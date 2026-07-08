import {useEffect, useRef, useState} from 'react';
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
  const wsStatus = useLiveSocketStore(s => s.status);
  const wsConnected = wsStatus === 'connected';

  const [offset, setOffset] = useState(0);
  const [lastAge, setLastAge] = useState(0);
  const [S, setS] = useState(emptyState);
  const [runSummary, setRunSummary] = useState(null);

  // 동시성 보호 — 폴링 중인 async chain이 완료되기 전 다음 poll이 들어오는 것 방지.
  // deps 최소화를 위해 S/offset/lastAge는 ref로 읽고 effect는 runId/wsConnected에만 의존.
  const pollingRef = useRef(false);
  const forcePollRef = useRef(false);
  const stateRef = useRef(S);        // 폴백 폴링이 읽는 최신 S
  const offsetRef = useRef(offset);  // 폴백 폴링이 읽는 최신 offset
  stateRef.current = S;
  offsetRef.current = offset;

  // runId 교체 시 상태 초기화
  useEffect(() => {
    setOffset(0);
    setLastAge(0);
    setS(emptyState());
    setRunSummary(null);
    offsetRef.current = 0;
    stateRef.current = emptyState();
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
  // overflow 메시지도 받아서, 즉시 폴백 폴링 1회 트리거.
  useEffect(() => {
    if (!runId) return;
    const unsubscribe = onLiveMessage((msg) => {
      if (msg.type === 'overflow') {
        // 강제 폴백 폴링 1회 — 폴링 effect가 다음 tick에 잡아서 실행.
        // WS가 연결돼 있어도 poll()을 한 번 돌려 누락된 이벤트를 채운다.
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

  // lastAge 단일 ticker — 의존성은 runId만. S.lastTs는 ref로 읽는다 (effect 재실행 회피).
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

  // 폴백 폴링 — WS 미연결일 때 주기 폴링, OR forcePollRef 세팅 시 1회 즉시 폴링.
  // 핵심: 의존성은 [runId, wsConnected]만. S/offset은 ref로 읽어 매 이벤트마다 effect가
  // 재실행되는 churn을 막는다 (과거 버그: S가 deps에 있어 매 이벤트마다 setInterval이
  // 재생성 + poll()이 매번 호출 + pollingRef race).
  useEffect(() => {
    if (!runId) return;

    async function poll() {
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
          // ref를 먼저 갱신 — 같은 tick에 다시 poll해도 최신 상태에서 이어짐.
          stateRef.current = nextState;
          offsetRef.current = nextOffset;
          setS(nextState);
          setOffset(nextOffset);
        }
        if (Number.isFinite(nextAge)) setLastAge(nextAge);
      } catch {
        // 다음 tick이 재시도
      } finally {
        pollingRef.current = false;
      }
    }

    // 강제 폴백(overflow) 시 즉시 1회 실행.
    if (forcePollRef.current) {
      forcePollRef.current = false;
      poll();
    }

    // 주기 인터벌 — WS 미연결이면 항상 poll, 연결 중이면 forcePollRef 감지만.
    const id = setInterval(() => {
      if (wsConnected) {
        if (forcePollRef.current) {
          forcePollRef.current = false;
          poll();
        }
      } else {
        // WS 끊김 — 매 tick마다 폴링 (overflow 강제도 같이 흡수).
        if (forcePollRef.current) forcePollRef.current = false;
        poll();
      }
    }, POLL_MS);
    return () => clearInterval(id);
  }, [runId, wsConnected]);

  return {S, lastAge, runSummary};
}
