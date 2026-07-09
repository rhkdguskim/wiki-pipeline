import {useEffect, useRef, useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {getEvents, getRunEventsSeq, getRunSummary} from '../api/client.js';
import {emptyState, ingest, mergeRunState} from '../lib/ingest.js';
import {onLiveMessage} from '../lib/liveBus.js';
import {useLiveSocketStore} from '../store/liveSocket.js';

const POLL_MS = 1500;
const SUMMARY_MS_LIVE = 30000;
const SUMMARY_MS_FALLBACK = 10000;
const STALL_TICK_MS = 5000;

export function useRunStream(runId) {
  const qc = useQueryClient();
  const wsStatus = useLiveSocketStore(s => s.status);
  const wsConnected = wsStatus === 'connected';

  const [offset, setOffset] = useState(0);
  const [lastSeq, setLastSeq] = useState(0);
  const [lastAge, setLastAge] = useState(0);
  const [S, setS] = useState(emptyState);
  const [runSummary, setRunSummary] = useState(null);
  const [summaryRefresh, setSummaryRefresh] = useState(0);

  const pollingRef = useRef(false);
  const forcePollRef = useRef(false);
  const stateRef = useRef(S);
  const offsetRef = useRef(offset);
  const lastSeqRef = useRef(lastSeq);
  stateRef.current = S;
  offsetRef.current = offset;
  lastSeqRef.current = lastSeq;

  useEffect(() => {
    setOffset(0);
    setLastSeq(0);
    setS(emptyState());
    setRunSummary(null);
    offsetRef.current = 0;
    lastSeqRef.current = 0;
    stateRef.current = emptyState();
  }, [runId]);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function fetchSummary() {
      try {
        const data = await getRunSummary(runId);
        if (cancelled) return;
        setRunSummary(data);
        // mergeRunState가 내부적으로 stateFromRunSummary를 호출하므로
        // 원본 summary(data)를 직접 전달 — 처리된 state를 넘기면
        // stages가 Map이 되어 stateFromRunSummary에서 .map() 크래시.
        setS((prev) => mergeRunState(prev, data));
        const last = Date.parse(data.last_event_at || '');
        setLastAge(Number.isFinite(last) ? Math.max(0, Math.floor((Date.now() - last) / 1000)) : 0);
      } catch {
      }
    }
    fetchSummary();
    const id = setInterval(fetchSummary, wsConnected ? SUMMARY_MS_LIVE : SUMMARY_MS_FALLBACK);
    return () => { cancelled = true; clearInterval(id); };
  }, [runId, wsConnected, summaryRefresh]);

  useEffect(() => {
    if (!runId) return;
    const unsubscribe = onLiveMessage((msg) => {
      if (msg.type === 'overflow') {
        forcePollRef.current = true;
        setSummaryRefresh((n) => n + 1);
        qc.invalidateQueries({queryKey: ['runSummary', runId]});
        return;
      }
      if (msg.type === 'run_status' && msg.run_id === runId) {
        setSummaryRefresh((n) => n + 1);
        qc.invalidateQueries({queryKey: ['runSummary', runId]});
        qc.invalidateQueries({queryKey: ['runQuality', runId]});
        qc.invalidateQueries({queryKey: ['mrPlan', runId]});
        return;
      }
      if ([
        'quality_updated', 'evidence_updated', 'coverage_updated',
        'artifact_updated', 'vnc_session_updated', 'mr_plan_updated',
      ].includes(msg.type) && msg.run_id === runId) {
        setSummaryRefresh((n) => n + 1);
      }
      if (msg.type === 'events' && msg.run_id === runId) {
        if (!msg.events?.length) return;
        setS((prev) => {
          let next = prev;
          for (const e of msg.events) next = ingest(next, e);
          return next;
        });
        if (typeof msg.latest_seq === 'number') {
          setLastSeq((cur) => Math.max(cur, msg.latest_seq));
          lastSeqRef.current = Math.max(lastSeqRef.current, msg.latest_seq);
        }
        if (typeof msg.snapshot_version === 'number') {
          if (msg.snapshot_version > (S.snapshotVersion || 0)) {
            qc.invalidateQueries({queryKey: ['runSummary', runId]});
          }
        }
        return;
      }
    });
    return unsubscribe;
  }, [runId, qc]);

  useEffect(() => {
    if (!runId) return;
    const tick = () => {
      const lastTs = stateRef.current.lastTs;
      setLastAge(lastTs ? Math.floor((Date.now() - lastTs) / 1000) : 0);
    };
    tick();
    const id = setInterval(tick, STALL_TICK_MS);
    return () => clearInterval(id);
  }, [runId]);

  useEffect(() => {
    if (!runId) return;

    async function pollSeq() {
      if (pollingRef.current) return;
      pollingRef.current = true;
      try {
        const data = await getRunEventsSeq(runId, lastSeqRef.current, 500);
        if (data.events?.length) {
          setS((prev) => {
            let next = prev;
            for (const e of data.events) next = ingest(next, e);
            return next;
          });
        }
        if (typeof data.latest_seq === 'number') {
          setLastSeq((cur) => Math.max(cur, data.latest_seq));
          lastSeqRef.current = Math.max(lastSeqRef.current, data.latest_seq);
        }
        if (data.truncated || data.has_more) {
          qc.invalidateQueries({queryKey: ['runSummary', runId]});
        }
      } catch {
      } finally {
        pollingRef.current = false;
      }
    }

    async function pollOffset() {
      if (pollingRef.current) return;
      pollingRef.current = true;
      try {
        let nextOffset = offsetRef.current;
        let nextAge = lastAge;
        let changed = false;
        let nextState = stateRef.current;
        for (let i = 0; i < 50; i++) {
          const data = await getEvents(runId, nextOffset);
          nextOffset = data.offset;
          nextAge = data.age_sec;
          for (const e of data.events) nextState = ingest(nextState, e);
          changed = data.events.length > 0 || changed;
          if (!data.events.length || data.offset >= data.size) break;
        }
        if (changed) {
          stateRef.current = nextState;
          offsetRef.current = nextOffset;
          setS(nextState);
          setOffset(nextOffset);
        }
        if (Number.isFinite(nextAge)) setLastAge(nextAge);
      } catch {
      } finally {
        pollingRef.current = false;
      }
    }

    if (forcePollRef.current) {
      forcePollRef.current = false;
      if (!wsConnected) pollOffset();
      else pollSeq();
    }

    const id = setInterval(() => {
      if (wsConnected) {
        if (forcePollRef.current) {
          forcePollRef.current = false;
          pollSeq();
        }
      } else {
        if (forcePollRef.current) forcePollRef.current = false;
        pollOffset();
      }
    }, POLL_MS);
    return () => clearInterval(id);
  }, [runId, wsConnected, qc, lastAge]);

  return {S, lastAge, runSummary, lastSeq, eventGapDetected: S.eventGapDetected};
}
