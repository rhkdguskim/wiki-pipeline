import {ChevronDown, GitBranch, PlayCircle} from 'lucide-react';
import {StatusPill} from '../components/StatusPill.jsx';
import {PageHeader} from '../components/PageHeader.jsx';
import {OverviewNarrative} from '../components/OverviewNarrative.jsx';
import {PipelineFlow} from '../components/PipelineFlow.jsx';
import {QualityGatePanel} from '../components/QualityGatePanel.jsx';
import {EvidencePackPanel} from '../components/EvidencePackPanel.jsx';
import {CoveragePanel} from '../components/CoveragePanel.jsx';
import {ArtifactSelectorPanel} from '../components/ArtifactSelectorPanel.jsx';
import {RemoteVncMonitor} from '../components/RemoteVncMonitor.jsx';
import {AgentQualityTimeline} from '../components/AgentQualityTimeline.jsx';
import {RunQualityBadge} from '../components/RunQualityBadge.jsx';
import {MrReadinessPanel} from '../components/MrReadinessPanel.jsx';
import {ChangeImpactPanel} from '../components/ChangeImpactPanel.jsx';
import {StagesPage} from './StagesPage.jsx';
import {TracePage} from './TracePage.jsx';
import {
  useRunQualityQuery, useRunEvidenceQuery, useRunCoverageQuery,
  useRunArtifactsQuery, useRunVncQuery, usePreflightArtifactMutation,
  useMrPlanQuery,
} from '../hooks/queries.js';
import {preflightArtifact} from '../api/client.js';
import {deriveStageState, fmtDur, STALL_SEC} from '../lib/format.js';
import {narrateStageLabel} from '../lib/stageNarrative.js';

const SUB_TABS = [
  {id: 'overview', label: '개요'},
  {id: 'quality', label: '품질'},
  {id: 'evidence', label: '근거'},
  {id: 'stages', label: '스테이지'},
  {id: 'coverage', label: '커버리지'},
  {id: 'artifacts', label: '산출물'},
  {id: 'remote', label: '원격 모니터'},
  {id: 'feed', label: '트레이스'},
];

// 파이프라인별로 강조할 탭. 매뉴얼 run 은 관측·산출물·원격 모니터가 핵심이다.
// 정적 run 에서 매뉴얼 전용 탭을 클릭하면 "적용되지 않음" 안내를 보여준다.
const TAB_PIPELINE_GATING = {
  coverage:  {pipeline: 'manual', offReason: '시나리오 커버리지는 매뉴얼 manual-automation run 에서 추적됩니다. 이 run 은 정적 docu-automation 입니다.'},
  artifacts: {pipeline: 'manual', offReason: '바이너리 산출물·아티팩트 배포 상태는 매뉴얼 manual-automation run 에서 추적됩니다. 이 run 은 정적 docu-automation 입니다.'},
  remote:    {pipeline: 'manual', offReason: '원격(mcp-vnc) 모니터링은 매뉴얼 manual-automation run 에서 사용됩니다. 이 run 은 정적 docu-automation 입니다.'},
};

const PIPELINE_LABEL = {static: '정적', manual: '매뉴얼', '': '-'};
const PIPELINE_BLURB = {
  static: '정적 docu-automation — 코드/문서 변경을 읽어 테마별 마크다운을 생성합니다.',
  manual: '매뉴얼 manual-automation — MCP 로 원격 앱을 관측하고 시나리오별 매뉴얼을 작성합니다.',
  '': '',
};

const STATUS_LABEL = {
  pending: '대기', running: '실행 중', done: '완료', failed: '실패',
  done_with_warnings: '경고 완료', failed_quality_gate: '품질 실패',
  partial: '부분 완료', stale: '지연', timeout: '시간 초과', cancelled: '취소',
};

export function MonitorPage({
  runId, setRunId, filteredRuns, dbRuns = [],
  selectedSource, setSelectedSource, sources,
  S, live, state, stages, activeRun, runSummary,
  mrPlan, mrBusy, mrMessage, onSubmitMr,
  monitorView, setMonitorView, onOpenRepositories,
  title = '모니터', eyebrow, description,
}) {
  // 파이프라인 플로우 — 메인 스테이지(layer==='stage')만 노출.
  // agent_step/engine_call 스테이지는 수가 많아 전부 표시하면 라벨이 잘리고
  // 중복된다. 상세는 '스테이지' 탭에서 본다.
  const flowStages = runId
    ? [...S.stages.entries()]
        .filter(([, s]) => s.layer === 'stage')
        .map(([key, s]) => {
          const {state: st, end} = deriveStageState(s, live);
          const dur = s.firstTs ? fmtDur((end || s.lastTs) - s.firstTs) : undefined;
          return {key, label: narrateStageLabel(key), status: st, dur};
        })
    : [];
  const doneCount = flowStages.filter(s => s.status === 'done').length;
  const total = flowStages.length;
  const elapsedMs = runId && S.firstTs ? (live ? Date.now() : S.lastTs) - S.firstTs : 0;

  // 파이프라인 종류 — run summary / activeRun / ingest state 셋 중 가장 신뢰성 있는 값.
  const pipelineId = (runSummary?.pipeline_id || activeRun?.pipeline_id || S.pipeline || '').toLowerCase();
  const isManualPipeline = pipelineId === 'manual';
  const pipelineLabel = PIPELINE_LABEL[pipelineId] || pipelineId || '-';
  const pipelineBlurb = PIPELINE_BLURB[pipelineId] || '';

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
      <span
        className={`pill small pipelineKindPill ${pipelineId === 'manual' ? 'warn' : ''}`}
        title={pipelineBlurb}
      >
        {pipelineLabel} 파이프라인
      </span>
      {pipelineBlurb && <span className="muted pipelineBlurb">{pipelineBlurb}</span>}
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
    {monitorView === 'quality' && runId && <QualityTab runId={runId} runSummary={runSummary} S={S} />}
    {monitorView === 'evidence' && runId && <EvidenceTab runId={runId} />}
    {monitorView === 'stages' && <StagesPage S={S} live={live} />}
    {monitorView === 'coverage' && runId && <CoverageTab
      runId={runId} isManual={isManualPipeline} pipelineId={pipelineId} />}
    {monitorView === 'artifacts' && runId && <ArtifactsTab
      runId={runId} runSummary={runSummary} isManual={isManualPipeline} pipelineId={pipelineId} />}
    {monitorView === 'remote' && runId && <RemoteTab
      runId={runId} isManual={isManualPipeline} pipelineId={pipelineId} />}
    {monitorView === 'feed' && <TracePage S={S} live={live} state={state} stages={stages} />}
  </div>;
}

/** 해당 탭이 활성화된 파이프라인 종류와 맞지 않을 때 보여주는 안내 카드. */
function PipelineNotApplicable({requiredPipeline, currentPipelineId, reason}) {
  return <div className="panel" style={{marginBottom: 12}}>
    <div className="emptyPanel">
      <strong>이 탭은 {requiredPipeline} 파이프라인 run 전용입니다</strong>
      <p className="muted">{reason}</p>
      <p className="muted small mono">
        현재 run pipeline_id={currentPipelineId || 'unknown'}
      </p>
    </div>
  </div>;
}

// ── Quality Tab ──────────────────────────────────────────────
function QualityTab({runId, runSummary, S}) {
  const qQuery = useRunQualityQuery(runId);
  const quality = qQuery.data?.quality || runSummary?.quality;
  const findings = qQuery.data?.findings || [];
  const agentSteps = [...S.feed.entries()].filter(([, e]) =>
    e.role || e.kind?.includes('agent') || e.kind?.includes('critic') ||
    e.kind?.includes('quality') || e.kind?.includes('repair')
  ).map(([id, e]) => ({id, ...e}));
  return <div>
    {runSummary && <div style={{marginBottom: 12}}>
      <RunQualityBadge summary={runSummary} />
    </div>}
    <QualityGatePanel quality={quality} findings={findings} />
    {agentSteps.length > 0 && <div style={{marginTop: 16}}>
      <div className="panelHead"><h2>에이전트 역할 타임라인</h2></div>
      <AgentQualityTimeline steps={agentSteps} />
    </div>}
  </div>;
}

// ── Evidence Tab ─────────────────────────────────────────────
function EvidenceTab({runId}) {
  const evQuery = useRunEvidenceQuery(runId);
  if (evQuery.isLoading) return <div className="muted">불러오는 중…</div>;
  if (evQuery.isError) return <div className="empty-state">근거 정보를 불러올 수 없습니다.</div>;
  return <EvidencePackPanel
    pack={evQuery.data}
    onItemClick={() => {}}
  />;
}

// ── Coverage Tab ─────────────────────────────────────────────
function CoverageTab({runId, isManual, pipelineId}) {
  if (!isManual) {
    return <PipelineNotApplicable
      requiredPipeline="매뉴얼"
      currentPipelineId={pipelineId}
      reason={TAB_PIPELINE_GATING.coverage.offReason}
    />;
  }
  const covQuery = useRunCoverageQuery(runId);
  if (covQuery.isLoading) return <div className="muted">불러오는 중…</div>;
  if (covQuery.isError) return <div className="empty-state">커버리지 정보를 불러올 수 없습니다.</div>;
  return <CoveragePanel coverage={covQuery.data} />;
}

// ── Artifacts Tab ────────────────────────────────────────────
function ArtifactsTab({runId, runSummary, isManual, pipelineId}) {
  if (!isManual) {
    return <PipelineNotApplicable
      requiredPipeline="매뉴얼"
      currentPipelineId={pipelineId}
      reason={TAB_PIPELINE_GATING.artifacts.offReason}
    />;
  }
  const artQuery = useRunArtifactsQuery(runId);
  const preflightMut = usePreflightArtifactMutation();
  const artifact = artQuery.data || runSummary?.artifact;
  const sourceId = runSummary?.source_id || '';
  return <div>
    {artQuery.isLoading && <div className="muted">불러오는 중…</div>}
    {artifact && artifact.available && <div className="panel" style={{marginBottom: 12}}>
      <div className="panelHead"><h2>아티팩트 상태</h2></div>
      <dl className="metaList">
        <dt>릴리스 태그</dt><dd className="mono">{artifact.release_tag || '-'}</dd>
        <dt>아티팩트</dt><dd className="mono">{artifact.artifact_name || '-'}</dd>
        <dt>설치 버전</dt><dd className="mono">{artifact.installed_version || '-'}</dd>
        <dt>빌드</dt><dd>{artifact.build_status || '-'}</dd>
        <dt>배포</dt><dd>{artifact.deploy_status || '-'}</dd>
        <dt>설치</dt><dd>{artifact.install_status || '-'}</dd>
        <dt>준비</dt><dd>{artifact.readiness_status || '-'}</dd>
        <dt>스모크</dt><dd>{artifact.smoke_status || '-'}</dd>
      </dl>
    </div>}
    {artifact && !artifact.available && <div className="panel" style={{marginBottom: 12}}>
      <div className="emptyPanel">
        <strong>아직 아티팩트 보고가 없습니다</strong>
        <p className="muted">runner 가 release/download/build/deploy/install 단계를 완료하면 여기에 표시됩니다. 매뉴얼 run 인 경우 release 트리거 또는 artifact selector 가 필요할 수 있습니다.</p>
      </div>
    </div>}
    {sourceId && <ArtifactSelectorPanel
      preflightResult={preflightMut.data}
      onPreflight={(payload) => preflightMut.mutate({sourceId, payload})}
      busy={preflightMut.isPending}
    />}
  </div>;
}

// ── Remote Monitor Tab ───────────────────────────────────────
function RemoteTab({runId, isManual, pipelineId}) {
  if (!isManual) {
    return <PipelineNotApplicable
      requiredPipeline="매뉴얼"
      currentPipelineId={pipelineId}
      reason={TAB_PIPELINE_GATING.remote.offReason}
    />;
  }
  const vncQuery = useRunVncQuery(runId);
  if (vncQuery.isLoading) return <div className="muted">불러오는 중…</div>;
  if (vncQuery.isError || !vncQuery.data) return <div className="empty-state">VNC 세션 정보를 불러올 수 없습니다.</div>;
  return <RemoteVncMonitor session={vncQuery.data} />;
}
