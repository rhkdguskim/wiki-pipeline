import {Bot, CalendarClock, Coins, LayoutGrid, Server, Settings, ShieldCheck, Workflow} from 'lucide-react';

const NAV = [
  {id: 'home', label: '홈', icon: LayoutGrid, key: '01'},
  {id: 'repositories', label: '저장소', icon: Server, key: '02'},
  {id: 'scheduler', label: '스케줄러', icon: CalendarClock, key: '03'},
  {id: 'pipelines', label: '파이프라인', icon: Workflow, key: '04'},
  {id: 'costs', label: '비용', icon: Coins, key: '05'},
  {id: 'audit', label: '감사', icon: ShieldCheck, key: '06'},
  {id: 'settings', label: '설정', icon: Settings, key: '07'},
];

export function SideNav({page, onNavigate}) {
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

  </aside>;
}
