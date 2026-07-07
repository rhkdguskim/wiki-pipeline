import {useEffect, useRef, useState} from 'react';
import {getEvents, getRunSummary} from '../api/client.js';
import {emptyState, ingest} from '../lib/ingest.js';
import {onLiveMessage} from '../lib/liveBus.js';
import {useLiveSocketStore} from '../store/liveSocket.js';

const POLL_MS = 1500;
const RUNS_MS = 10000;

// runId 기반 실시간 스트림. WS가 연결돼 있으면 useLiveSocket이 push하는 이벤트만 신뢰하고
// 폴링을 멈춘다. WS가 끊기면(fallback) 기존 offset 프로토콜 폴링으로 되돌아간다.
// run-summary는 항상 주기 폴링(가벼운 요약 스냅샷이라 WS로 스트리밍하지 않음).
export function useRunStream(runId) {
  const wsStatus = useLiveSocketStore(s => s.status);
  const wsConnected = wsStatus === 'connected';

  const [offset, setOffset] = useState(0);
  const [lastAge, setLastAge] = useState(0);
  const [S, setS] = useState(emptyState);
  const [runSummary, setRunSummary] = useState(null);
  const polling = useRef(false);

  useEffect(() => {
    setOffset(0);
    setLastAge(0);
    setS(emptyState());
    setRunSummary(null);
  }, [runId]);

  // run-summary는 WS 연결 여부와 무관하게 주기 폴링 (경량 스냅샷)
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function fetchSummary() {
      try {
        const data = await getRunSummary(runId);
        if (!cancelled) setRunSummary(data);
      } catch {
        // projection is optional; live tail still works
      }
    }
    fetchSummary();
    const id = setInterval(fetchSummary, RUNS_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [runId]);

  // WS 이벤트 구독 — 선택된 runId와 일치하는 events 메시지만 ingest에 반영
  useEffect(() => {
    if (!runId) return;
    const unsubscribe = onLiveMessage((msg) => {
      if (msg.type !== 'events' || msg.run_id !== runId) return;
      if (!msg.events?.length) return;
      setS(prev => {
        let next = prev;
        for (const e of msg.events) next = ingest(next, e);
        return next;
      });
    });
    return unsubscribe;
  }, [runId]);

  // WS 모드에서는 폴링이 age_sec를 주지 않으므로, lastTs 기준 경과 시간을 직접 갱신해
  // stall 감지(runState)가 계속 동작하게 한다.
  useEffect(() => {
    if (!runId || !wsConnected) return;
    const tick = () => {
      setLastAge(S.lastTs ? Math.floor((Date.now() - S.lastTs) / 1000) : 0);
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [runId, wsConnected, S.lastTs]);

  // 폴링 폴백 — WS 미연결 상태일 때만 동작 (offset 프로토콜)
  useEffect(() => {
    if (!runId || wsConnected) return;
    async function poll() {
      if (!runId || polling.current) return;
      polling.current = true;
      try {
        let nextOffset = offset;
        let nextAge = lastAge;
        let changed = false;
        let nextState = S;
        for (let i = 0; i < 50; i++) {
          const data = await getEvents(runId, nextOffset);
          if (data.error) break;
          nextOffset = data.offset;
          nextAge = data.age_sec;
          for (const e of data.events) nextState = ingest(nextState, e);
          changed ||= data.events.length > 0;
          if (data.offset >= data.size) break;
        }
        setOffset(nextOffset);
        setLastAge(nextAge);
        if (changed) setS(nextState);
      } catch {
        // next poll retries
      } finally {
        polling.current = false;
      }
    }
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, [runId, offset, lastAge, S, wsConnected]);

  return {S, lastAge, runSummary};
}
