import {Bot} from 'lucide-react';

export function SourceRail({sources, selected, onSelect}) {
  return <aside className="rail">
    <div className="brand"><Bot size={18} /><span>Agent Ops</span></div>
    <div className="railSection">
      <div className="railLabel">Agent Sources</div>
      {sources.length ? sources.map(s => <button key={s.id} className={selected === s.id ? 'sourceBtn active' : 'sourceBtn'} onClick={() => onSelect(s.id)}>
        <Bot size={15} />
        <span><strong>{s.label}</strong><small>{s.kind} · {s.project_id}</small></span>
      </button>) : <div className="railEmpty">등록 없음</div>}
    </div>
  </aside>;
}
