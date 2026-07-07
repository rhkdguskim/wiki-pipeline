import {fmtNum, runStateLabel} from '../lib/format.js';

export function MissionKpis({S, stages, state}) {
  const done = stages.filter(s => s.status === 'done').length;
  const total = stages.length || 0;
  const completion = total ? Math.round((done / total) * 100) : 0;
  const toolReliability = S.toolCalls ? Math.round(((S.toolCalls - S.toolErr) / S.toolCalls) * 100) : 100;
  const burn = S.inTok + S.outTok;
  return <div className="missionKpis">
    <div><span>Completion</span><strong>{completion}%</strong><small>{done}/{total} stages</small></div>
    <div><span>Token burn</span><strong>{fmtNum(burn)}</strong><small>in + out</small></div>
    <div><span>Tool reliability</span><strong>{toolReliability}%</strong><small>{S.toolErr} failures</small></div>
    <div><span>Run health</span><strong>{runStateLabel(state)}</strong><small>{S.retries ? `${S.retries} retries` : 'no retries'}</small></div>
  </div>;
}
