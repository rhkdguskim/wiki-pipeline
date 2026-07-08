import {useEffect, useRef} from 'react';
import {useQueryClient} from '@tanstack/react-query';
import {emitLiveMessage} from '../lib/liveBus.js';
import {useLiveSocketStore} from '../store/liveSocket.js';
import {useUiStore} from '../store/ui.js';

const MAX_BACKOFF_MS = 15000;

function wsUrl(verbose, types) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = localStorage.getItem('cp_token');
  const params = new URLSearchParams();
  if (token) params.set('token', token);
  params.set('verbose', verbose ? '1' : '0');
  if (types && types.length > 0) params.set('types', types.join(','));
  return `${proto}//${location.host}/api/ws?${params.toString()}`;
}

export function useLiveSocket() {
  const qc = useQueryClient();
  const setStatus = useLiveSocketStore(s => s.setStatus);
  const noteEvent = useLiveSocketStore(s => s.noteEvent);
  const bumpReconnect = useLiveSocketStore(s => s.bumpReconnect);
  const pushToast = useUiStore(s => s.pushToast);
  const wsVerbose = useUiStore(s => s.wsVerbose);
  const backoffRef = useRef(1000);
  const closedByUsRef = useRef(false);

  useEffect(() => {
    closedByUsRef.current = false;
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
        try { socket.close(); } catch {}
      };
    }

    connect();
    return () => {
      closedByUsRef.current = true;
      clearTimeout(retryTimer);
      try { socket?.close(); } catch {}
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
      qc.invalidateQueries({queryKey: ['pipelineStatus']});
      qc.invalidateQueries({queryKey: ['overview']});
      qc.invalidateQueries({queryKey: ['costs']});
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
        qc.invalidateQueries({queryKey: ['mrPlan', msg.run_id]});
      }
      emitLiveMessage(msg);
      if (msg.status === 'done' && msg.mr_url) {
        pushToast('문서 생성 완료 — MR 검토하기', 'success');
      } else if (msg.status === 'done_with_warnings') {
        pushToast('문서 생성 완료 (경고 포함) — review 필요', 'warning');
      } else if (msg.status === 'failed_quality_gate') {
        pushToast('품질 게이트 실패 — MR 제출 차단', 'error');
      } else if (msg.status === 'failed' || msg.status === 'timeout') {
        pushToast(`run 실패: ${msg.run_id || ''}`, 'error');
      } else if (msg.stale_complete) {
        pushToast('run 이 stale 상태로 종료되었습니다 — sha 가 전진하지 않았습니다', 'warning');
      } else if (msg.status === 'done' && msg.source_disabled) {
        pushToast('소스가 자동 비활성화됐습니다 — 담당자에게 알림이 발송됐습니다', 'error');
      }
      return;
    case 'quality_updated':
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
        qc.invalidateQueries({queryKey: ['runQuality', msg.run_id]});
      }
      qc.invalidateQueries({queryKey: ['qualitySummary']});
      qc.invalidateQueries({queryKey: ['pipelineStatus']});
      qc.invalidateQueries({queryKey: ['overview']});
      emitLiveMessage(msg);
      return;
    case 'evidence_updated':
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runEvidence', msg.run_id]});
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
      }
      emitLiveMessage(msg);
      return;
    case 'coverage_updated':
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runCoverage', msg.run_id]});
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
      }
      qc.invalidateQueries({queryKey: ['pipelineStatus']});
      emitLiveMessage(msg);
      return;
    case 'artifact_updated':
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runArtifacts', msg.run_id]});
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
      }
      emitLiveMessage(msg);
      return;
    case 'vnc_session_updated':
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runVnc', msg.run_id]});
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
      }
      emitLiveMessage(msg);
      return;
    case 'mr_plan_updated':
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['mrPlan', msg.run_id]});
      }
      emitLiveMessage(msg);
      return;
    case 'run_heartbeat':
      emitLiveMessage(msg);
      return;
    case 'runs_changed':
      qc.invalidateQueries({queryKey: ['runs']});
      qc.invalidateQueries({queryKey: ['dbRuns']});
      return;
    case 'sources_changed':
      qc.invalidateQueries({queryKey: ['sources']});
      qc.invalidateQueries({queryKey: ['manualProfile']});
      qc.invalidateQueries({queryKey: ['scenarios']});
      return;
    case 'instances_changed':
      qc.invalidateQueries({queryKey: ['instances']});
      return;
    case 'targets_changed':
      qc.invalidateQueries({queryKey: ['docTargets']});
      return;
    case 'pipeline_status_changed':
      qc.invalidateQueries({queryKey: ['pipelineStatus']});
      return;
    case 'costs_changed':
      qc.invalidateQueries({queryKey: ['costs']});
      return;
    case 'overflow':
      emitLiveMessage(msg);
      if (msg.run_id) {
        qc.invalidateQueries({queryKey: ['runSummary', msg.run_id]});
        qc.invalidateQueries({queryKey: ['runEvents', msg.run_id]});
      } else {
        qc.invalidateQueries({queryKey: ['dbRuns']});
        qc.invalidateQueries({queryKey: ['pipelineStatus']});
        qc.invalidateQueries({queryKey: ['overview']});
      }
      pushToast('실시간 채널 큐 overflow — fallback polling 으로 전환', 'warning');
      return;
    default:
  }
}
