import {Bot, Coins, History, LayoutGrid, Radio, Server} from 'lucide-react';
import {TokenSettings} from './TokenSettings.jsx';

const NAV = [
  {id: 'home', label: '홈', icon: LayoutGrid},
  {id: 'repositories', label: '저장소', icon: Server},
  {id: 'monitor', label: '모니터', icon: Radio},
  {id: 'runs', label: '실행 이력', icon: History},
  {id: 'costs', label: '비용', icon: Coins},
];

export function SideNav({page, onNavigate, health, liveStatus}) {
  const liveOk = liveStatus === 'connected';
  const liveLabel = liveOk ? '실시간 연결됨' : liveStatus === 'connecting' ? '연결 중…' : '폴링 모드';
  return <aside className="rail">
    <div className="brand"><Bot size={18} /><span>Agent Ops</span></div>
    <nav className="navList">
      {NAV.map(({id, label, icon: Icon}) => (
        <button key={id} className={page === id ? 'navBtn active' : 'navBtn'} onClick={() => onNavigate(id)}>
          <Icon size={16} /><span>{label}</span>
        </button>
      ))}
    </nav>
    <div className="railFoot">
      <div className="railFootRow">
        <span className={`healthDot ${liveOk ? 'ok' : 'bad'}`} title={liveLabel} />
        <small>{liveLabel}</small>
      </div>
      <div className="railFootRow">
        <span className={`healthDot ${health?.ok ? 'ok' : 'bad'}`} title={health ? `auth=${health.auth} secretbox=${health.secretbox}` : '상태 확인 중'} />
        <small>{health?.ok ? '서버 정상' : '서버 확인 필요'}</small>
        <TokenSettings />
      </div>
    </div>
  </aside>;
}
