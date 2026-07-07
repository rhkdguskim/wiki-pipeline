import {CheckCircle2, FileText, GitPullRequest, Radio, XCircle} from 'lucide-react';
import {narrateStage} from '../lib/stageNarrative.js';
import {fmtDur, fmtNum} from '../lib/format.js';

function currentSentence({state, S, runSummary, activeRun}) {
  if (state === 'done') {
    const count = runSummary?.generated?.length ?? [...S.stages.values()].filter(s => s.status === 'done').length;
    return {tone: 'done', text: `문서 ${count}건 생성을 마쳤어요`};
  }
  if (state === 'failed') {
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

export function OverviewNarrative({S, live, state, stages, activeRun, runSummary, mrPlan, mrBusy, mrMessage, onSubmitMr, onOpenTrace}) {
  const sentence = currentSentence({state, S, runSummary, activeRun});
  const {total, done, pct, unitLabel} = progressInfo({stages, S, runSummary});
  const elapsedMs = S.firstTs ? (live ? Date.now() : S.lastTs) - S.firstTs : 0;
  const generated = runSummary?.generated || [];
  const mrUrl = activeRun?.mr_url;
  const canSubmit = !mrUrl && state === 'done' && mrPlan?.can_submit;

  return <div className="narrative">
    <section className={`narrativeCard ${sentence.tone}`}>
      <div className="narrativeOrb">
        {sentence.tone === 'done' && <CheckCircle2 size={22} />}
        {sentence.tone === 'failed' && <XCircle size={22} />}
        {(sentence.tone === 'running' || sentence.tone === 'stalled') && <span className="spinner" />}
      </div>
      <div>
        <strong>{sentence.text}</strong>
        {sentence.detail && <p className="narrativeDetail">{sentence.detail}</p>}
      </div>
    </section>

    <section className="panel">
      <div className="progressHead">
        <span>진행률</span>
        <span>{pct}% {unitLabel && `· ${unitLabel}`}</span>
      </div>
      <div className="progressBar"><div className="progressFill" style={{width: `${pct}%`}} /></div>
      <div className="progressFoot">
        <span>{done}/{total} 단계 완료</span>
        <span>경과 {fmtDur(elapsedMs)}</span>
      </div>
    </section>

    <section className="panel">
      <div className="panelHead"><h2><FileText size={14} />만들어진 문서</h2></div>
      {generated.length ? <ul className="docList">
        {generated.map((g, i) => <li key={`${g.path}-${i}`}>
          <FileText size={14} />
          <span className="docName mono">{g.path}</span>
          {g.warned ? <span className="pill stalled small">경고</span> : <span className="pill done small">통과</span>}
        </li>)}
      </ul> : <div className="emptyPanel">아직 생성된 문서가 없어요</div>}
      {mrUrl && <a className="primaryBtn fullBtn" href={mrUrl} target="_blank" rel="noreferrer">
        <GitPullRequest size={15} />MR에서 검토하기 →
      </a>}
      {canSubmit && <button type="button" className="primaryBtn fullBtn" disabled={mrBusy} onClick={onSubmitMr}>
        <GitPullRequest size={15} />문서 MR로 제출하기
      </button>}
      {mrMessage && <p className="formMessage">{mrMessage}</p>}
    </section>

    <button type="button" className="narrativeFootnote" onClick={onOpenTrace}>
      <Radio size={12} />LLM 호출 {S.llmCalls}회 · 토큰 {fmtNum(S.inTok + S.outTok)}
    </button>
  </div>;
}
