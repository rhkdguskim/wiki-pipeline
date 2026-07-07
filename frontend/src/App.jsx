import {useEffect, useMemo, useState} from 'react';
import {Activity, Bot, Braces, ChevronDown, Clock3, GitBranch, Layers3, PlayCircle, SquareTerminal} from 'lucide-react';
import {useUiStore} from './store/ui.js';
import {
  useSourcesQuery, useInstancesQuery, useDocTargetsQuery, useRunsQuery, useDbRunsQuery,
  useCostsQuery, useOverviewQuery, useHealthQuery, useMrPlanQuery,
  useSaveSourceMutation, useVerifySourceMutation, useSaveInstanceMutation,
  useSaveDocTargetMutation, useTriggerRunMutation, useSubmitMrMutation,
} from './hooks/queries.js';
import {useRunStream} from './hooks/useRunStream.js';
import {STALL_SEC, fmtDur, fmtNum, nf, runState} from './lib/format.js';
import {blankSource, blankInstance, defaultDocTarget} from './lib/defaults.js';

import {Stat} from './components/Stat.jsx';
import {StatusPill} from './components/StatusPill.jsx';
import {SourceRail} from './components/SourceRail.jsx';
import {TokenSettings} from './components/TokenSettings.jsx';
import {SourceWizard} from './components/SourceWizard.jsx';

import {RunPage} from './pages/RunPage.jsx';
import {StagesPage} from './pages/StagesPage.jsx';
import {TracePage} from './pages/TracePage.jsx';
import {SourcesPage} from './pages/SourcesPage.jsx';
import {RunsPage} from './pages/RunsPage.jsx';
import {CostsPage} from './pages/CostsPage.jsx';

const TABS = [
  {id: 'overview', label: 'Run'},
  {id: 'stages', label: 'Plan'},
  {id: 'feed', label: 'Trace'},
  {id: 'sources', label: 'Sources'},
  {id: 'runs', label: 'Runs'},
  {id: 'costs', label: 'Costs'},
];

export function App() {
  const {selectedSource, setSelectedSource, runId, setRunId, tab, setTab, wizardOpen, openWizard, closeWizard} = useUiStore();

  const {data: sources = []} = useSourcesQuery();
  const {data: instances = []} = useInstancesQuery();
  const {data: docTargetsData} = useDocTargetsQuery();
  const {data: runs = []} = useRunsQuery();
  const {data: dbRuns = []} = useDbRunsQuery();
  const {data: costs} = useCostsQuery();
  const {data: overview} = useOverviewQuery();
  const {data: health} = useHealthQuery();

  const docTargets = docTargetsData?.targets || [];

  const [sourceForm, setSourceForm] = useState(blankSource);
  const [targetForm, setTargetForm] = useState(defaultDocTarget);
  const [instanceForm, setInstanceForm] = useState(blankInstance);
  const [verifyResult, setVerifyResult] = useState(null);
  const [query, setQuery] = useState('');
  const [actionMessage, setActionMessage] = useState('');

  useEffect(() => {
    if (docTargets.length && targetForm === defaultDocTarget) setTargetForm(docTargets[0]);
  }, [docTargets]);

  const saveSourceMutation = useSaveSourceMutation();
  const verifySourceMutation = useVerifySourceMutation();
  const saveInstanceMutation = useSaveInstanceMutation();
  const saveDocTargetMutation = useSaveDocTargetMutation();
  const triggerRunMutation = useTriggerRunMutation();
  const submitMrMutation = useSubmitMrMutation();

  const {S, lastAge, runSummary} = useRunStream(runId);
  const mrPlanQuery = useMrPlanQuery(runId, 'product-common');
  const mrPlan = mrPlanQuery.data;

  useEffect(() => {
    if (!runId && runs.length) setRunId(runs[0].run_id);
  }, [runs, runId]);

  const filteredRuns = useMemo(() => runs.filter(r => selectedSource === 'all' || r.source_id === selectedSource), [runs, selectedSource]);
  const activeRun = runs.find(r => r.run_id === runId);
  const [state] = runState(S, lastAge);
  const live = state === 'running' || state === 'stalled';
  const stages = [...S.stages.values()].filter(s => s.status != null);
  const done = stages.filter(s => s.status === 'done').length;
  const failed = stages.filter(s => s.status === 'failed').length;
  const visibleSources = sources.filter(s => !query || `${s.label} ${s.project_id} ${s.id}`.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    if (!filteredRuns.length) return;
    if (!filteredRuns.some(r => r.run_id === runId)) setRunId(filteredRuns[0].run_id);
  }, [filteredRuns, runId]);

  const saveSource = async () => {
    setActionMessage('');
    try {
      const existing = sources.some(s => s.id === sourceForm.id);
      const data = await saveSourceMutation.mutateAsync({form: sourceForm, existing});
      setActionMessage(`source 저장 완료: ${data.label}`);
    } catch (e) {
      setActionMessage(e.message);
    }
  };

  const saveDocTarget = async () => {
    setActionMessage('');
    try {
      const id = targetForm.id || 'product-common';
      const existing = docTargets.some(t => t.id === id);
      const data = await saveDocTargetMutation.mutateAsync({form: {...targetForm, id}, existing});
      setActionMessage(`docs-hub target 저장 완료: ${data.label}`);
    } catch (e) {
      setActionMessage(e.message);
    }
  };

  const saveInstance = async () => {
    setActionMessage('');
    try {
      const existing = !!instanceForm.id;
      const data = await saveInstanceMutation.mutateAsync({form: instanceForm, existing});
      setActionMessage(`instance 저장 완료: ${data.label || data.id}`);
    } catch (e) {
      setActionMessage(e.message);
    }
  };

  const doVerifySource = async (id) => {
    const targetId = id || sourceForm.id;
    if (!targetId) return;
    setActionMessage('');
    try {
      const result = await verifySourceMutation.mutateAsync(targetId);
      setVerifyResult(result);
    } catch (e) {
      setVerifyResult({verified: false, error: e.message});
    }
  };

  const doTriggerRun = async (sourceId) => {
    setActionMessage('');
    try {
      const data = await triggerRunMutation.mutateAsync({sourceId, mode: 'auto'});
      setRunId(data.run_id);
      setTab('overview');
    } catch (e) {
      setActionMessage(e.message);
    }
  };

  const doSubmitMr = async () => {
    if (!runId) return;
    try {
      await submitMrMutation.mutateAsync({runId, target: 'product-common'});
    } catch {
      // mutation error surfaced via submitMrMutation.error in MrPlanPanel message
    }
  };

  const selectSourceForEdit = (s) => {
    setSourceForm({...s, themes: (s.themes || []).join(','), token: ''});
    setVerifyResult(null);
  };

  return (
    <div className="app">
      <SourceRail sources={sources} selected={selectedSource} onSelect={setSelectedSource} />
      <main className="main">
        <header className="topbar">
          <div>
            <h1>Agent View</h1>
            <p>{activeRun?.source_id || 'legacy'} · {S.pipeline || 'pipeline'} · {runId || 'run 대기'}</p>
          </div>
          <div className="toolbar">
            <label className="selectWrap"><GitBranch size={15} /><select value={selectedSource} onChange={e => setSelectedSource(e.target.value)}>
              <option value="all">전체 source</option>
              {sources.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select><ChevronDown size={14} /></label>
            <label className="selectWrap"><PlayCircle size={15} /><select value={runId} onChange={e => setRunId(e.target.value)}>
              {filteredRuns.map(r => <option key={r.run_id} value={r.run_id}>{r.run_id}{r.age_sec < STALL_SEC ? ' ●' : ''}</option>)}
            </select><ChevronDown size={14} /></label>
            <span className={`healthDot ${health?.ok ? 'ok' : 'bad'}`} title={health ? `auth=${health.auth} secretbox=${health.secretbox}` : '상태 확인 중'} />
            <TokenSettings />
            <StatusPill state={state} />
          </div>
        </header>

        <section className="stats">
          <Stat label="입력 토큰" value={fmtNum(S.inTok)} hint={S.inTok ? nf.format(S.inTok) : ''} icon={Braces} />
          <Stat label="출력 토큰" value={fmtNum(S.outTok)} hint={S.outTok ? nf.format(S.outTok) : ''} icon={Bot} />
          <Stat label="LLM 호출" value={nf.format(S.llmCalls)} hint={S.retries ? `재시도 ${S.retries}` : ''} icon={Activity} />
          <Stat label="도구 호출" value={nf.format(S.toolCalls)} hint={S.toolErr ? `실패 ${S.toolErr}` : ''} icon={SquareTerminal} />
          <Stat label="스테이지" value={`${done}/${stages.length}`} hint={failed ? `실패 ${failed}` : '완료/전체'} icon={Layers3} />
          <Stat label="경과" value={fmtDur(S.firstTs ? (live ? Date.now() : S.lastTs) - S.firstTs : 0)} hint={lastAge ? `${lastAge}s age` : ''} icon={Clock3} />
        </section>

        <nav className="tabs">
          {TABS.map(({id, label}) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>)}
        </nav>

        {tab === 'overview' && <RunPage
          S={S} live={live} state={state} stages={stages} activeRun={activeRun}
          runSummary={runSummary} mrPlan={mrPlan} mrBusy={submitMrMutation.isPending}
          mrMessage={submitMrMutation.error?.message || (submitMrMutation.data?.result?.merge_request?.web_url ? `MR 생성 완료: ${submitMrMutation.data.result.merge_request.web_url}` : '')}
          onSubmitMr={doSubmitMr} onRefreshMr={() => mrPlanQuery.refetch()}
        />}
        {tab === 'stages' && <StagesPage S={S} live={live} />}
        {tab === 'feed' && <TracePage feed={S.feed} />}
        {tab === 'sources' && <SourcesPage
          visibleSources={visibleSources}
          query={query}
          onQueryChange={setQuery}
          onNewSource={() => setSourceForm(blankSource)}
          onOpenWizard={openWizard}
          onSelectSource={selectSourceForEdit}
          sourceForm={sourceForm}
          onSourceFormChange={setSourceForm}
          onSaveSource={saveSource}
          onVerifySource={doVerifySource}
          onTriggerSource={doTriggerRun}
          saveBusy={saveSourceMutation.isPending || saveInstanceMutation.isPending || saveDocTargetMutation.isPending}
          saveMessage={actionMessage}
          verifyResult={verifyResult}
          targetForm={targetForm}
          onTargetFormChange={setTargetForm}
          onSaveTarget={saveDocTarget}
          instances={instances}
          instanceForm={instanceForm}
          onInstanceFormChange={setInstanceForm}
          onSaveInstance={saveInstance}
        />}
        {tab === 'runs' && <RunsPage rows={dbRuns} onSelect={id => { setRunId(id); setTab('overview'); }} onTrigger={doTriggerRun} sources={sources} />}
        {tab === 'costs' && <CostsPage costs={costs} overview={overview} />}
      </main>

      {wizardOpen && <SourceWizard
        onClose={closeWizard}
        onCreated={() => setActionMessage('소스 등록 완료')}
        onTriggerSuggested={doTriggerRun}
      />}
    </div>
  );
}
