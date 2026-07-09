import {useState, Suspense, lazy} from 'react';
import {AlertTriangle, CheckCircle2, Eye, FileText, GitPullRequest, Radio, XCircle} from 'lucide-react';
import {narrateStage} from '../lib/stageNarrative.js';
import {fmtDur, fmtNum} from '../lib/format.js';
import {RunQualityBadge} from './RunQualityBadge.jsx';
import {VncSessionBadge} from './VncSessionBadge.jsx';
import {ChangeImpactPanel} from './ChangeImpactPanel.jsx';
import {MrReadinessPanel} from './MrReadinessPanel.jsx';
import {useRunDocsQuery} from '../hooks/queries.js';

const DocViewer = lazy(() => import('./DocViewer.jsx').then(m => ({default: m.DocViewer})));

function currentSentence({state, S, runSummary, activeRun}) {
  if (state === 'done') {
    const count = runSummary?.generated?.length ?? [...S.stages.values()].filter(s => s.status === 'done').length;
    const failedStages = runSummary?.kpi?.stage_failed || 0;
    if (failedStages > 0) {
      return {tone: 'partial', text: `문서 ${count}건은 만들었지만 일부 단계가 실패했어요`,
              detail: '진행률 아래에서 실패한 단계를 확인하세요'};
    }
    return {tone: 'done', text: `문서 ${count}건 생성을 마쳤어요`};
  }
  if (state === 'done_with_warnings') {
    return {tone: 'warning', text: '문서 생성 완료 — 경고가 있어요', detail: 'MR 제출 전 review 가 필요합니다'};
  }
  if (state === 'failed_quality_gate') {
    return {tone: 'failed', text: '품질 게이트 실패 — MR 제출이 차단됐어요', detail: activeRun?.blocked_reason || ''};
  }
  if (state === 'partial') {
    return {tone: 'partial', text: '일부 산출물만 유효해요', detail: activeRun?.blocked_reason || ''};
  }
  if (state === 'stale') {
    return {tone: 'failed', text: 'stale complete — sha pointer 가 달라 전진하지 않았어요', detail: activeRun?.error || ''};
  }
  if (state === 'failed' || state === 'timeout') {
    const lastError = runSummary?.errors?.at(-1);
    const cause = lastError?.message || activeRun?.error || '';
    return {tone: 'failed', text: '문제가 발생해 중단됐어요 — 담당자에게 알림이 발송됩니다', detail: cause};
  }
  const runningEntry = [...S.stages.entries()].reverse().find(([, s]) => s.status === 'running');
  const stageName = runSummary?.current_stage || runningEntry?.[0] || [...S.stages.keys()].at(-1) || '';
  if (!stageName) return {tone: state === 'stalled' ? 'stalled' : 'running', text: '작업을 준비하고 있어요'};
  return {tone: state === 'stalled' ? 'stalled' : 'running', text: narrateStage(stageName)};
}

function progressInfo({stages, S, runSummary}) {
  const total = runSummary?.kpi?.stage_total ?? stages.length;
  const done = runSummary?.kpi?.stage_done ?? stages.filter(s => s.status === 'done').length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const runningStage = [...S.stages.entries()].reverse().find(([, s]) => s.status === 'running');
  const progress = runningStage?.[1]?.progress;
  const unitLabel = progress?.unit ? `${progress.n}/${progress.m} ${progress.unit}` : '';
  return {total, done, pct, unitLabel};
}

export function OverviewNarrative({S, live, state, stages, activeRun, runSummary, mrPlan, mrBusy, mrMessage, onSubmitMr, onOpenTrace, runId}) {
  const [docViewer, setDocViewer] = useState(null);  // {path} | null
  const sentence = currentSentence({state, S, runSummary, activeRun});
  const {total, done, pct, unitLabel} = progressInfo({stages, S, runSummary});
  const elapsedMs = S.firstTs ? (live ? Date.now() : S.lastTs) - S.firstTs : 0;

  // DB 기반 문서 목록 — run_summary.generated 보다 정확하고 최신.
  // docu-automation(static) · manual-automation 산출물 모두 포함.
  // runId 가 없거나 run 이 진행 중일 수 있으므로 enabled 는 runId 존재 여부에만 의존.
  const docsQuery = useRunDocsQuery(runId, !!runId);
  const dbDocs = docsQuery.data?.docs || [];
  // DB 목록이 있으면 우선, 없으면 runSummary.generated 로 폴백 (run 진행 중 webhook 전).
  const generated = dbDocs.length ? dbDocs.map(d => ({
    path: d.path,
    theme: d.theme,
    warned: (d.warning_count || 0) > 0,
    verdict: d.quality_status || '',
    has_content: d.has_content,
    content_size: d.content_size || 0,
    quality_status: d.quality_status || 'not_evaluated',
    pipeline_id: runSummary?.pipeline_id || '',
  })) : (runSummary?.generated || []).map(g => ({
    ...g,
    has_content: true,
    content_size: 0,
    quality_status: g.verdict || '',
  }));

  const modelUsage = runSummary?.usage_by_model?.length ? runSummary.usage_by_model : [...(S.modelUsage || new Map()).values()];
  const topModel = modelUsage.slice().sort((a, b) => (
    ((b.input_tokens || 0) + (b.output_tokens || 0)) - ((a.input_tokens || 0) + (a.output_tokens || 0))
  ))[0];
  const mrUrl = activeRun?.mr_url;
  const publishState = runSummary?.publish_state || (state === 'done' ? 'publishable' : 'unknown');
  const canSubmit = !mrUrl && ['done', 'done_with_warnings'].includes(state) &&
    mrPlan?.can_submit && publishState !== 'blocked';

  return <div className="narrative">
    <section className={`narrativeCard ${sentence.tone}`}>
      <div className="narrativeOrb">
        {sentence.tone === 'done' && <CheckCircle2 size={22} />}
        {sentence.tone === 'failed' && <XCircle size={22} />}
        {(sentence.tone === 'partial' || sentence.tone === 'warning') && <AlertTriangle size={22} />}
        {(sentence.tone === 'running' || sentence.tone === 'stalled') && <span className="spinner" />}
      </div>
      <div>
        <strong>{sentence.text}</strong>
        {sentence.detail && <p className="narrativeDetail">{sentence.detail}</p>}
        {(runSummary?.quality || runSummary?.vnc) && (
          <div className="narrative__badges">
            {runSummary?.quality && <RunQualityBadge summary={runSummary} compact />}
            {runSummary?.vnc && <VncSessionBadge session={runSummary.vnc} />}
          </div>
        )}
      </div>
    </section>

    <section className="panel">
      <div className="progressHead">
        <span>진행률</span>
        <span>{pct}% {unitLabel && `· ${unitLabel}`}</span>
      </div>
      <div className="progressBar"><div className={`progressFill ${sentence.tone === 'partial' ? 'warn' : ''}`} style={{width: `${pct}%`}} /></div>
      <div className="progressFoot">
        <span>{done}/{total} 단계 완료</span>
        <span>경과 {fmtDur(elapsedMs)}</span>
      </div>
    </section>

    {runSummary?.changed_files && (
      <section className="panel">
        <div className="panelHead"><h2>변경 영향</h2></div>
        <ChangeImpactPanel summary={{
          changed_files: runSummary.changed_files,
          affected_themes: runSummary.affected_themes || [],
          skipped_themes: runSummary.skipped_themes || [],
          from_sha: runSummary.from_sha,
          to_sha: runSummary.to_sha,
        }} />
      </section>
    )}

    <section className="panel">
      <div className="panelHead"><h2><FileText size={14} />만들어진 문서</h2><span className="coordTag">{generated.length} DOCS</span></div>
      {generated.length ? <ul className="docList">
        {generated.map((g, i) => {
          const isMd = /\.(md|markdown)$/i.test(g.path || '');
          const qs = g.quality_status || g.verdict || '';
          const isFail = qs === 'fail';
          const isWarn = qs === 'warning' || g.warned;
          // 콘텐츠가 DB 에 있으면 클릭 가능, 아니면 디스크 폴백 시도.
          const canView = isMd && (g.has_content !== false);
          return <li key={`${g.path}-${i}`} className={canView ? 'docItem clickable' : ''} onClick={canView ? () => setDocViewer({path: g.path}) : undefined} title={canView ? '클릭하여 미리보기' : (isMd ? '콘텐츠를 불러올 수 없습니다' : '')}>
            <FileText size={14} />
            <span className="docName mono">{g.path}</span>
            {canView && <Eye size={12} className="docViewHint" aria-hidden="true" />}
            {isFail ? <span className="pill failed small">실패</span>
              : isWarn ? <span className="pill stalled small">경고</span>
              : <span className="pill done small">통과</span>}
          </li>;
        })}
      </ul> : <div className="emptyPanel">아직 생성된 문서가 없어요</div>}
      {mrUrl && <a className="primaryBtn fullBtn" href={mrUrl} target="_blank" rel="noreferrer">
        <GitPullRequest size={15} />MR에서 검토하기 →
      </a>}
      {canSubmit && <button type="button" className="primaryBtn fullBtn" disabled={mrBusy} onClick={onSubmitMr}>
        <GitPullRequest size={15} />{publishState === 'review_required' ? '문서 MR로 제출 (검토 필요)' : '문서 MR로 제출하기'}
      </button>}
      {publishState === 'blocked' && !mrUrl && <div className="emptyPanel"><AlertTriangle size={14} /> {
        // run이 품질 게이트 도달 전에 실패한 경우, 게이트 실패 메시지가 오해를 일으킨다.
        // failed/timeout/cancelled 등 실행 자체가 중단된 경우를 구분해 표시.
        ['failed', 'timeout', 'cancelled'].includes(state)
          ? '실행 실패로 MR 제출이 불가능합니다'
          : (runSummary?.blocked_reason || '품질 게이트 실패로 MR 제출이 차단됐습니다')
      }</div>}
      {mrMessage && <p className="formMessage">{mrMessage}</p>}
    </section>

    {mrPlan && (
      <section className="panel">
        <div className="panelHead"><h2><GitPullRequest size={14} />MR 준비 상태</h2></div>
        <MrReadinessPanel plan={mrPlan} onSubmit={canSubmit ? onSubmitMr : null} busy={mrBusy} />
      </section>
    )}

    <button type="button" className="narrativeFootnote" onClick={onOpenTrace}>
      <Radio size={12} />LLM 호출 {S.llmCalls}회 · 토큰 {fmtNum(S.inTok + S.outTok)}{topModel?.model ? ` · ${topModel.provider}/${topModel.model}` : ''}
    </button>

    {docViewer && runId && (
      <Suspense fallback={<div className="docViewerOverlay"><div className="docViewer"><div className="docViewerBody loading">로드 중…</div></div></div>}>
        <DocViewer runId={runId} path={docViewer.path} onClose={() => setDocViewer(null)} />
      </Suspense>
    )}
  </div>;
}
