import {Bot, Coins, LayoutGrid, Radio, Server, Settings, ShieldCheck, Workflow} from 'lucide-react';
import {useLiveSocketStore} from '../store/liveSocket.js';
import {useUiStore} from '../store/ui.js';
import {TokenSettings} from './TokenSettings.jsx';

const NAV = [
  {id: 'home', label: '홈', icon: LayoutGrid, key: '01'},
  {id: 'repositories', label: '저장소', icon: Server, key: '02'},
  {id: 'monitor', label: '모니터', icon: Radio, key: '03'},
  {id: 'pipelines', label: '파이프라인', icon: Workflow, key: '04'},
  {id: 'costs', label: '비용', icon: Coins, key: '05'},
  {id: 'audit', label: '감사', icon: ShieldCheck, key: '06'},
  {id: 'settings', label: '설정', icon: Settings, key: '07'},
];

function fmtRelative(ms) {
  if (!ms) return '-';
  const sec = Math.floor((Date.now() - ms) / 1000);
  if (sec < 5) return '방금';
  if (sec < 60) return `${sec}s 전`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m 전`;
  return `${Math.floor(sec / 3600)}h 전`;
}

export function SideNav({page, onNavigate, health, healthReady}) {
  // liveSocket 상태를 직접 구독 — App.jsx를 거치지 않고 사이드바 푸터가 표시.
  const status = useLiveSocketStore(s => s.status);
  const lastEventAt = useLiveSocketStore(s => s.lastEventAt);
  const messageCount = useLiveSocketStore(s => s.messageCount);
  const reconnectAttempts = useLiveSocketStore(s => s.reconnectAttempts);
  // ENT-E: WS verbose 토글 — useUiStore 가 localStorage 에 보존.
  const wsVerbose = useUiStore(s => s.wsVerbose);
  const setWsVerbose = useUiStore(s => s.setWsVerbose);

  const liveOk = status === 'connected';
  const liveConnecting = status === 'connecting';
  const liveLabel = liveOk ? '실시간 연결' : liveConnecting ? '연결 중' : '폴링 모드';
  const liveHint = liveOk
    ? `마지막 이벤트 ${fmtRelative(lastEventAt)} · 메시지 ${messageCount}건`
    : liveConnecting
      ? '서버와 연결을 시도하는 중'
      : reconnectAttempts > 0
        ? `재연결 시도 ${reconnectAttempts}회 · 폴링으로 보정`
        : '연결 끊김 · 폴링 모드';

  const healthKnown = !!health;
  const healthOk = health?.ok;
  const healthLabel = !healthKnown
    ? 'BOOT'
    : healthOk && (!health.auth || !health.secretbox)
      ? 'DEV MODE'
      : healthOk
        ? 'OK'
        : 'CHECK';
  const healthTitle = healthKnown ? `db=${health.db} auth=${health.auth} secretbox=${health.secretbox}` : '상태 확인 중';

  // ENT-D: deep health. ready 가 down 이면 'degraded' 표시. 단순한 점 색.
  const readyKnown = !!healthReady;
  const readyOk = healthReady?.status === 'ok';
  const dbCheck = healthReady?.checks?.db;
  const readyLabel = !readyKnown ? '…' : readyOk ? 'READY' : 'DEGRADED';
  const readyTitle = !readyKnown
    ? '/health/ready 확인 중'
    : readyOk
      ? `DB · 스케줄러 · 브로드캐스터 모두 정상`
      : Object.entries(healthReady?.checks || {})
          .filter(([_, v]) => v && !v.ok)
          .map(([k, v]) => `${k}: ${v.detail || 'fail'}`)
          .join(' / ') || 'degraded';

  return <aside className="rail">
    <div className="brand">
      <span className="brandMark" aria-hidden="true"><Bot size={16} /></span>
      <span>Agent Ops</span>
      <small>v1</small>
    </div>

    <div>
      <div className="navSectionLabel" aria-hidden="true">Navigation</div>
      <nav className="navList" aria-label="주요 탐색">
        {NAV.map(({id, label, icon: Icon, key}) => (
          <button
            key={id}
            type="button"
            className={page === id ? 'navBtn active' : 'navBtn'}
            onClick={() => onNavigate(id)}
            aria-current={page === id ? 'page' : undefined}
          >
            <Icon size={15} />
            <span>{label}</span>
            <span className="navKey" aria-hidden="true">{key}</span>
          </button>
        ))}
      </nav>
    </div>

    <div className="railFoot">
      <label className="railVerboseToggle" title="agent_step.thinking 이벤트 포함 여부 — 모니터링 노이즈를 줄이려면 끄세요.">
        <input
          type="checkbox"
          checked={wsVerbose}
          onChange={e => setWsVerbose(e.target.checked)}
        />
        <span>WS verbose</span>
        <small className="muted">{wsVerbose ? 'on' : 'off'}</small>
      </label>
      <div className="railSignalRow" title={liveHint}>
        <span className={`healthDot ${liveOk ? 'ok' : liveConnecting ? '' : 'bad'}`} aria-hidden="true" />
        <small>{liveLabel}</small>
        {reconnectAttempts > 0 && !liveOk && <span className="railBadge" aria-label={`재연결 ${reconnectAttempts}회`}>{reconnectAttempts}</span>}
      </div>
      <div className="railSignalRow" title={healthTitle}>
        <span className={`healthDot ${healthOk ? 'ok' : healthKnown ? 'bad' : ''}`} aria-hidden="true" />
        <small>서버 {healthLabel}</small>
        <TokenSettings />
      </div>
      <div className="railSignalRow" title={readyTitle}>
        <span className={`healthDot ${readyOk ? 'ok' : readyKnown ? 'bad' : ''}`} aria-hidden="true" />
        <small>ready {readyLabel}</small>
        {dbCheck && !dbCheck.ok && <span className="railBadge">DB</span>}
      </div>
      {liveOk && messageCount > 0 && (
        <div className="railMetaRow" title={`마지막 이벤트 ${fmtRelative(lastEventAt)}`}>
          <small className="railMeta">LAST EVT {fmtRelative(lastEventAt)}</small>
        </div>
      )}
    </div>
  </aside>;
}
