import {useEffect, useRef} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {emitLiveMessage} from '../lib/liveBus.js';
import {useLiveSocketStore} from '../store/liveSocket.js';
import {useUiStore} from '../store/ui.js';

const MAX_BACKOFF_MS = 15000;

function wsUrl(verbose) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = localStorage.getItem('cp_token');
  const params = new URLSearchParams();
  if (token) params.set('token', token);
  // verbose 가 바뀌면 다른 WS 쿼리 파라미터를 써야 재연결이 일어난다 — useLiveSocket
  // 은 wsVerbose 를 의존성으로 잡으므로, 값이 바뀌면 cleanup → 재연결.
  params.set('verbose', verbose ? '1' : '0');
  return `${proto}//${location.host}/api/ws?${params.toString()}`;
}

// 앱 루트에서 1회만 마운트 — 러너 이벤트/런 상태/레지스트리 변경을 실시간 push로 받는다.
// 연결이 끊기면 지수 백오프(1s~15s)로 재연결하고, 그동안은 각 훅이 폴링으로 폴백한다.
// overflow 메시지를 받으면 선택 runId의 useRunStream이 즉시 폴백 폴링을 1회 돌게 한다.
export function useLiveSocket() {
  const qc = useQueryClient();
  const setStatus = useLiveSocketStore(s => s.setStatus);
  const noteEvent = useLiveSocketStore(s => s.noteEvent);
  const bumpReconnect = useLiveSocketStore(s => s.bumpReconnect);
  const pushToast = useUiStore(s => s.pushToast);
  const wsVerbose = useUiStore(s => s.wsVerbose);  // verbose 토글 변경 시 재연결
  const backoffRef = useRef(1000);
  const closedByUsRef = useRef(false);

  useEffect(() => {
    let socket;
    let retryTimer;

    function connect() {
      setStatus('connecting');
      socket = new WebSocket(wsUrl(wsVerbose));

      socket.onopen = () => {
        backoffRef.current = 1000;
        setStatus('connected');
      };

      socket.onmessage = (ev) => {
        noteEvent();
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        handleMessage(msg, {qc, pushToast, emitLiveMessage});
      };

      socket.onclose = () => {
        setStatus('fallback');
        if (closedByUsRef.current) return;
        bumpReconnect();
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
  }, [qc, setStatus, noteEvent, bumpReconnect, pushToast, wsVerbose]);
}

function handleMessage(msg, ctx) {
  const {qc, pushToast, emitLiveMessage} = ctx;
  switch (msg.type) {
    case 'events':
      emitLiveMessage(msg);
      return;
    case 'run_status':
      qc.invalidateQueries({queryKey: ['runs']});
      qc.invalidateQueries({queryKey: ['dbRuns']});
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
        qc.invalidateQueries({queryKey: ['mrPlan', msg.run_id]});
      }
      emitLiveMessage(msg);
      if (msg.status === 'done' && msg.mr_url) {
        pushToast('문서 생성 완료 — MR 검토하기', 'success');
      } else if (msg.status === 'failed') {
        pushToast(`run 실패: ${msg.run_id || ''}`, 'error');
      } else if (msg.status === 'done' && msg.source_disabled) {
        pushToast('소스가 자동 비활성화됐습니다 — 담당자에게 알림이 발송됐습니다', 'error');
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
      // 큐 넘침 — 구독자(useRunStream)가 폴백 폴링 1회 돌게 하고, 전체 쿼리도 refresh.
      // run_id가 있으면 그 run만, 없으면 모든 활성 run 쿼리를 무효화.
      emitLiveMessage(msg);
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
        qc.invalidateQueries({queryKey: ['events', msg.run_id]});
      } else {
        qc.invalidateQueries({queryKey: ['dbRuns']});
      }
      return;
    default:
  }
}
