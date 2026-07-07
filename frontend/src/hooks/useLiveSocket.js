import {useEffect, useRef} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {emitLiveMessage} from '../lib/liveBus.js';
import {useLiveSocketStore} from '../store/liveSocket.js';
import {useUiStore} from '../store/ui.js';

const MAX_BACKOFF_MS = 15000;

function wsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = localStorage.getItem('cp_token');
  const qs = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${proto}//${location.host}/api/ws${qs}`;
}

// 앱 루트에서 1회만 마운트 — 러너 이벤트/런 상태/레지스트리 변경을 실시간 push로 받는다.
// 연결이 끊기면 지수 백오프(1s~15s)로 재연결하고, 그동안은 각 훅이 폴링으로 폴백한다.
export function useLiveSocket() {
  const qc = useQueryClient();
  const setStatus = useLiveSocketStore(s => s.setStatus);
  const pushToast = useUiStore(s => s.pushToast);
  const backoffRef = useRef(1000);
  const closedByUsRef = useRef(false);

  useEffect(() => {
    let socket;
    let retryTimer;

    function connect() {
      setStatus('connecting');
      socket = new WebSocket(wsUrl());

      socket.onopen = () => {
        backoffRef.current = 1000;
        setStatus('connected');
      };

      socket.onmessage = (ev) => {
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        handleMessage(msg, {qc, pushToast});
      };

      socket.onclose = () => {
        setStatus('fallback');
        if (closedByUsRef.current) return;
        retryTimer = setTimeout(connect, backoffRef.current);
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();
    return () => {
      closedByUsRef.current = true;
      clearTimeout(retryTimer);
      socket?.close();
    };
  }, [qc, setStatus, pushToast]);
}

function handleMessage(msg, {qc, pushToast}) {
  switch (msg.type) {
    case 'events':
      emitLiveMessage(msg);
      return;
    case 'run_status':
      qc.invalidateQueries({queryKey: ['runs']});
      qc.invalidateQueries({queryKey: ['dbRuns']});
      if (msg.run_id) qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
      emitLiveMessage(msg);
      if (msg.status === 'done' && msg.mr_url) {
        pushToast('문서 생성 완료 — MR 검토하기', 'success');
      } else if (msg.status === 'failed') {
        pushToast(`run 실패: ${msg.run_id || ''}`, 'error');
      }
      return;
    case 'runs_changed':
      qc.invalidateQueries({queryKey: ['runs']});
      qc.invalidateQueries({queryKey: ['dbRuns']});
      return;
    case 'sources_changed':
      qc.invalidateQueries({queryKey: ['sources']});
      return;
    case 'instances_changed':
      qc.invalidateQueries({queryKey: ['instances']});
      return;
    case 'targets_changed':
      qc.invalidateQueries({queryKey: ['docTargets']});
      return;
    case 'overflow':
      // 큐 넘침 — 소켓을 닫아 재연결을 유도, 그동안 폴링이 데이터를 보정한다.
      emitLiveMessage(msg);
      return;
    default:
  }
}
