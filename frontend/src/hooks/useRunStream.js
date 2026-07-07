import {useEffect, useRef, useState} from 'react';
import {getEvents, getRunSummary} from '../api/client.js';
import {emptyState, ingest} from '../lib/ingest.js';

const POLL_MS = 1500;
const RUNS_MS = 10000;

// runId 기반 events 증분 폴링(offset 프로토콜) + ingest 리듀서 + run-summary 주기 폴링
export function useRunStream(runId) {
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

  useEffect(() => {
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
  }, [runId, offset, lastAge, S]);

  return {S, lastAge, runSummary};
}
