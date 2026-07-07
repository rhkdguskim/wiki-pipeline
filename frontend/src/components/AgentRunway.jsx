import {fmtDur, runStateLabel} from '../lib/format.js';

export function AgentRunway({S, live}) {
  const rows = [...S.stages.entries()].sort((a, b) => a[1].firstTs - b[1].firstTs).slice(-8);
  if (!rows.length) return <div className="runway emptyPanel">이벤트 대기 중</div>;
  return <div className="runway">
    {rows.map(([name, s]) => {
      const active = s.status === 'running' || (s.status == null && live && Date.now() - s.lastTs < 45000);
      const state = active ? 'running' : (s.status || 'idle');
      return <div className={`node ${state}`} key={name}>
        <span className="nodeOrb" />
        <div>
          <strong>{name}</strong>
          <small>{runStateLabel(state) || '작업'} · {fmtDur((active && live ? Date.now() : s.lastTs) - s.firstTs)}</small>
        </div>
      </div>;
    })}
  </div>;
}
