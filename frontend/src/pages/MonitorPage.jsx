import {ChevronDown, GitBranch, PlayCircle} from 'lucide-react';
import {StatusPill} from '../components/StatusPill.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {OverviewNarrative} from '../components/OverviewNarrative.jsx';
import {PipelineFlow} from '../components/PipelineFlow.jsx';
import {StagesPage} from './StagesPage.jsx';
import {TracePage} from './TracePage.jsx';
import {deriveStageState, fmtDur, STALL_SEC} from '../lib/format.js';
import {narrateStageLabel} from '../lib/stageNarrative.js';

const SUB_TABS = [
  {id: 'overview', label: '개요'},
  {id: 'stages', label: '스테이지'},
  {id: 'feed', label: '트레이스'},
];

const STATUS_LABEL = {pending: '대기', running: '실행 중', done: '완료', failed: '실패'};

export function MonitorPage({
  runId, setRunId, filteredRuns, dbRuns = [],
  selectedSource, setSelectedSource, sources,
  S, live, state, stages, activeRun, runSummary,
  mrPlan, mrBusy, mrMessage, onSubmitMr,
  monitorView, setMonitorView, onOpenRepositories,
  title = '모니터', eyebrow, description,
}) {
  // 파이프라인 플로우 — S.stages 맵에서 노드/링크 상태를 계산.
  const flowStages = runId
    ? [...S.stages.entries()].map(([key, s]) => {
        const {state: st, end} = deriveStageState(s, live);
        const dur = s.firstTs ? fmtDur((end || s.lastTs) - s.firstTs) : undefined;
        return {key, label: narrateStageLabel(key), status: st, dur};
      })
    : [];
  const doneCount = flowStages.filter(s => s.status === 'done').length;
  const total = flowStages.length;
  const elapsedMs = runId && S.firstTs ? (live ? Date.now() : S.lastTs) - S.firstTs : 0;

  return <div>
    <PageHeader
      eyebrow={eyebrow || (runId ? `RUN · ${runId.slice(0, 12)}` : 'MONITOR')}
      title={title}
      description={description || (runId ? '선택한 run의 실시간 진행 흐름' : '저장소별 run 현황과 최근 활동을 한눈에')}
      actions={<>
        <label className="selectWrap"><GitBranch size={15} /><select value={selectedSource} onChange={e => setSelectedSource(e.target.value)}>
          <option value="all">전체 소스</option>
          {sources.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select><ChevronDown size={14} /></label>
        {runId && (
          <label className="selectWrap"><PlayCircle size={15} /><select value={runId} onChange={e => setRunId(e.target.value)}>
            <option value="">run 선택</option>
            {filteredRuns.map(r => <option key={r.run_id} value={r.run_id}>{r.run_id}{r.age_sec < STALL_SEC ? ' ●' : ''}</option>)}
          </select><ChevronDown size={14} /></label>
        )}
      </>}
    />

    <div className="monitorHead">
      <StatusPill state={state} />
      <span className="contextTitle mono">{runId}</span>
      <span className="muted">{activeRun?.source_id || '-'}</span>
    </div>

    {flowStages.length > 0 && (
      <PipelineFlow
        stages={flowStages}
        meta={[
          {label: 'STAGES', value: `${doneCount}/${total}`},
          {label: 'ELAPSED', value: fmtDur(elapsedMs)},
        ]}
      />
    )}

    <nav className="tabs">
      {SUB_TABS.map(({id, label}) => (
        <button key={id} className={monitorView === id ? 'active' : ''} onClick={() => setMonitorView(id)}>
          {label}
        </button>
      ))}
    </nav>

    {monitorView === 'overview' && <OverviewNarrative
      S={S} live={live} state={state} stages={stages} activeRun={activeRun}
      runSummary={runSummary} mrPlan={mrPlan} mrBusy={mrBusy} mrMessage={mrMessage}
      onSubmitMr={onSubmitMr} onOpenTrace={() => setMonitorView('feed')}
      runId={runId}
    />}
    {monitorView === 'stages' && <StagesPage S={S} live={live} />}
    {monitorView === 'feed' && <TracePage S={S} live={live} state={state} stages={stages} />}
  </div>;
}
