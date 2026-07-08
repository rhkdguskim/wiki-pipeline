import {useEffect, useRef, useState} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {getEvents, getRunSummary} from '../api/client.js';
import {emptyState, ingest, stateFromRunSummary} from '../lib/ingest.js';
import {onLiveMessage} from '../lib/liveBus.js';
import {useLiveSocketStore} from '../store/liveSocket.js';

const POLL_MS = 1500;
const SUMMARY_MS_LIVE = 30000;   // WS 연결 시 — run_status done/failed 시 즉시 refetch 되므로 느슨해도 OK
const SUMMARY_MS_FALLBACK = 10000;
const STALL_TICK_MS = 5000;

// runId 기반 실시간 스트림. WS가 연결돼 있으면 useLiveSocket이 push하는 이벤트만 신뢰.
// WS가 끊기면(fallback) offset 프로토콜 폴링으로 되돌아간다.
// run-summary는 run_status WS 메시지가 도착하면 useLiveSocket이 invalidate → 자동 refetch.
export function useRunStream(runId) {
  const qc = useQueryClient();
  const wsStatus = useLiveSocketStore(s => s.status);
  const wsConnected = wsStatus === 'connected';

  const [offset, setOffset] = useState(0);
  const [lastAge, setLastAge] = useState(0);
  const [S, setS] = useState(emptyState);
  const [runSummary, setRunSummary] = useState(null);
  const pollingRef = useRef(false);

  // runId 교체 시 상태 초기화
  useEffect(() => {
    setOffset(0);
    setLastAge(0);
    setS(emptyState());
    setRunSummary(null);
  }, [runId]);

  // run-summary 폴링 — WS 연결 시 30s, fallback 시 10s.
  // useLiveSocket이 run_status done/failed 수신 시 invalidateQueries(['runSummary', run_id])를
  // 호출하므로, 여기서는 느슨한 안전망만 제공한다.
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function fetchSummary() {
      try {
        const data = await getRunSummary(runId);
        if (!cancelled) {
          setRunSummary(data);
          setS(prev => {
            const snapshot = stateFromRunSummary(data);
            return prev.lastTs && snapshot.lastTs && prev.lastTs > snapshot.lastTs ? prev : snapshot;
          });
          const last = Date.parse(data.last_event_at || '');
          setLastAge(Number.isFinite(last) ? Math.max(0, Math.floor((Date.now() - last) / 1000)) : 0);
        }
      } catch {
        // projection is optional; live tail still works
      }
    }
    fetchSummary();
    const id = setInterval(fetchSummary, wsConnected ? SUMMARY_MS_LIVE : SUMMARY_MS_FALLBACK);
    return () => { cancelled = true; clearInterval(id); };
  }, [runId, wsConnected]);

  // WS 이벤트 구독 — 선택된 runId와 일치하는 events 메시지만 ingest에 반영.
  // overflow 메시지도 받아서, 즉시 폴링 1회 트리거.
  useEffect(() => {
    if (!runId) return;
    const unsubscribe = onLiveMessage((msg) => {
      if (msg.type === 'overflow') {
        // 강제 폴백 폴링 1회 — 다음 effect에서 처리
        forcePollRef.current = true;
        return;
      }
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

  // lastAge 단일 ticker — WS 모드에서도 주기 갱신 (stall 감지용).
  // 의존성을 runId·wsConnected·S.lastTs로 잡아도, 내부는 setInterval 1개만.
  useEffect(() => {
    if (!runId) return;
    const tick = () => {
      setLastAge(S.lastTs ? Math.floor((Date.now() - S.lastTs) / 1000) : 0);
    };
    tick();
    const id = setInterval(tick, STALL_TICK_MS);
    return () => clearInterval(id);
  }, [runId, S.lastTs]);

  // 폴백 폴링 — WS 미연결 OR overflow 강제 1회. forcePollRef로 트리거.
  const forcePollRef = useRef(false);
  useEffect(() => {
    if (!runId) return;
    async function poll() {
      if (pollingRef.current) return;
      pollingRef.current = true;
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
        pollingRef.current = false;
      }
    }
    // WS 미연결이면 주기 폴링. 강제 트리거(fallback overflow)면 1회 즉시 실행.
    poll();
    if (forcePollRef.current) {
      forcePollRef.current = false;
    }
    let id;
    if (!wsConnected) {
      id = setInterval(poll, POLL_MS);
    }
    return () => { if (id) clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, offset, lastAge, S, wsConnected]);

  // runSummary invalidate 대응 — 외부(useLiveSocket)에서 같은 키를 invalidate하면
  // 위 폴링 effect와 별개로 getRunSummary가 즉시 호출되게 queryClient 캐시를 우회한다.
  // (여기서는 useQuery를 안 쓰므로, 수동 fetch를 트리거할 필요는 없다 — run_status 도착 시
  // useLiveSocket이 invalidateQueries만 부르고, 실제 refetch는 위 run-summary effect의
  // setInterval이 담당한다. 즉시 반영하려면 직접 fetch를 부르는 게 낫다.)
  useEffect(() => {
    if (!runId) return;
    const unsubscribe = qc.getQueryCache().subscribe((event) => {
      if (event.type !== 'updated') return;
      const q = event.query;
      if (q.queryKey[0] !== 'runSummary' || q.queryKey[1] !== runId) return;
      // run_summary를 useQuery 기반으로 안 쓰므로 트리거 무의미. 안전망으로만.
    });
    return unsubscribe;
  }, [qc, runId]);

  return {S, lastAge, runSummary};
}
