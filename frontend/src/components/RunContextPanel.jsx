import {nf} from '../lib/format.js';
import {StatusPill} from './StatusPill.jsx';
import {MrPlanPanel} from './MrPlanPanel.jsx';
import {TokenChart} from './TokenChart.jsx';

export function RunContextPanel({S, activeRun, state, stages, summary, mrPlan, mrBusy, mrMessage, onSubmitMr, onRefreshMr}) {
  const runningStage = [...S.stages.entries()].reverse().find(([, s]) => s.status === 'running');
  const kpi = summary?.kpi;
  const tools = summary?.tools || [];
  const artifacts = summary?.artifacts || [];
  const errors = summary?.errors || [];
  return <aside className="contextPanel">
    <section>
      <span className="contextLabel">Session</span>
      <strong className="contextTitle">{activeRun?.run_id || 'run 대기'}</strong>
      <StatusPill state={state} />
    </section>
    <section>
      <span className="contextLabel">Current stage</span>
      <strong className="contextTitle mono">{runningStage?.[0] || [...S.stages.keys()].at(-1) || '-'}</strong>
    </section>
    <section className="contextGrid">
      <span>LLM</span><strong>{nf.format(kpi?.llm_calls ?? S.llmCalls)}</strong>
      <span>Tools</span><strong>{nf.format(kpi?.tool_calls ?? S.toolCalls)}</strong>
      <span>Errors</span><strong>{nf.format(kpi?.errors ?? (S.toolErr + (state === 'failed' ? 1 : 0)))}</strong>
      <span>Stages</span><strong>{kpi ? `${kpi.stage_done}/${kpi.stage_total}` : `${stages.filter(s => s.status === 'done').length}/${stages.length}`}</strong>
    </section>
    <section>
      <span className="contextLabel">Top tools</span>
      <div className="miniList">
        {tools.slice(0, 5).length ? tools.slice(0, 5).map(t => <span key={t.name}><b>{t.name}</b><em>{t.calls}</em></span>) : <small>tool data 없음</small>}
      </div>
    </section>
    <section>
      <span className="contextLabel">Artifacts</span>
      <div className="miniList">
        {artifacts.slice(0, 5).length ? artifacts.slice(0, 5).map(a => <span key={a.path}><b>{a.name}</b><em>{fmtNum(a.size)}B</em></span>) : <small>artifact 없음</small>}
      </div>
    </section>
    <section>
      <MrPlanPanel plan={mrPlan} busy={mrBusy} message={mrMessage} onSubmit={onSubmitMr} onRefresh={onRefreshMr} />
    </section>
    {!!errors.length && <section>
      <span className="contextLabel">Recent errors</span>
      <div className="errorList">
        {errors.slice(-3).map((e, i) => <p key={`${e.stage}-${i}`}><b>{e.stage}</b>{e.message || e.kind}</p>)}
      </div>
    </section>}
    <section>
      <span className="contextLabel">Token flow</span>
      <TokenChart series={S.series} />
    </section>
  </aside>;
}
