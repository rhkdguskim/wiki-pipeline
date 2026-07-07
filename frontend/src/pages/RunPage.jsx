import {StatusPill} from '../components/StatusPill.jsx';
import {AgentRunway} from '../components/AgentRunway.jsx';
import {MissionKpis} from '../components/MissionKpis.jsx';
import {AgentConversation} from '../components/AgentConversation.jsx';
import {RunContextPanel} from '../components/RunContextPanel.jsx';

export function RunPage({S, live, state, stages, activeRun, runSummary, mrPlan, mrBusy, mrMessage, onSubmitMr, onRefreshMr}) {
  return <div className="agentGrid">
    <section className="agentStage">
      <div className="agentHead">
        <div>
          <span className="eyebrow">Autonomous run</span>
          <h2>{S.pipeline || 'static'} agent</h2>
        </div>
        <StatusPill state={state} />
      </div>
      <AgentRunway S={S} live={live} />
      <MissionKpis S={S} stages={stages} state={state} />
      <AgentConversation feed={S.feed} />
    </section>
    <RunContextPanel
      S={S}
      activeRun={activeRun}
      state={state}
      stages={stages}
      summary={runSummary}
      mrPlan={mrPlan}
      mrBusy={mrBusy}
      mrMessage={mrMessage}
      onSubmitMr={onSubmitMr}
      onRefreshMr={onRefreshMr}
    />
  </div>;
}
