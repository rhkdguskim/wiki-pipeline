import {useEffect, useMemo, useState} from 'react';
import {useUiStore} from './store/ui.js';
import {
  useSourcesQuery, useInstancesQuery, useDocTargetsQuery, useRunsQuery, useDbRunsQuery,
  useSourceRunsQuery, useCostsQuery, useOverviewQuery, useHealthQuery, useMrPlanQuery,
  useSaveSourceMutation, useVerifySourceMutation, useSaveInstanceMutation,
  useSaveDocTargetMutation, useTriggerRunMutation, useSubmitMrMutation,
  useCreateSourceScheduleMutation, useUpdateSourceScheduleMutation,
  useDeleteSourceScheduleMutation,
} from './hooks/queries.js';
import {useRunStream} from './hooks/useRunStream.js';
import {useLiveSocket} from './hooks/useLiveSocket.js';
import {useLiveSocketStore} from './store/liveSocket.js';
import {runState} from './lib/format.js';
import {blankSource, blankInstance, defaultDocTarget} from './lib/defaults.js';

import {SideNav} from './components/SideNav.jsx';
import {SourceWizard} from './components/SourceWizard.jsx';
import {Toasts} from './components/Toasts.jsx';

import {HomePage} from './pages/HomePage.jsx';
import {MonitorPage} from './pages/MonitorPage.jsx';
import {RepositoriesPage} from './pages/RepositoriesPage.jsx';
import {SourceDetailPage} from './pages/SourceDetailPage.jsx';
import {RunsPage} from './pages/RunsPage.jsx';
import {CostsPage} from './pages/CostsPage.jsx';

export function App() {
  const {
    page, setPage, selectedSource, setSelectedSource, runId, setRunId,
    monitorView, setMonitorView, sourceDetailId, openSourceDetail, closeSourceDetail,
    wizardOpen, openWizard, closeWizard, pushToast,
  } = useUiStore();

  useLiveSocket();
  const liveStatus = useLiveSocketStore(s => s.status);

  const sourcesQuery = useSourcesQuery();
  const instancesQuery = useInstancesQuery();
  const docTargetsQuery = useDocTargetsQuery();
  const runsQuery = useRunsQuery();
  const dbRunsQuery = useDbRunsQuery();
  const sourceRunsQuery = useSourceRunsQuery(sourceDetailId);
  const costsQuery = useCostsQuery();
  const overviewQuery = useOverviewQuery();
  const {data: health} = useHealthQuery();

  const sources = sourcesQuery.data || [];
  const instances = instancesQuery.data || [];
  const runs = runsQuery.data || [];
  const dbRuns = dbRunsQuery.data || [];
  const docTargets = docTargetsQuery.data?.targets || [];

  const [sourceForm, setSourceForm] = useState(blankSource);
  const [targetForm, setTargetForm] = useState(defaultDocTarget);
  const [instanceForm, setInstanceForm] = useState(blankInstance);
  const [verifyResult, setVerifyResult] = useState(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (docTargets.length && targetForm === defaultDocTarget) setTargetForm(docTargets[0]);
  }, [docTargets]);

  const saveSourceMutation = useSaveSourceMutation();
  const verifySourceMutation = useVerifySourceMutation();
  const saveInstanceMutation = useSaveInstanceMutation();
  const saveDocTargetMutation = useSaveDocTargetMutation();
  const triggerRunMutation = useTriggerRunMutation();
  const submitMrMutation = useSubmitMrMutation();
  const createScheduleMutation = useCreateSourceScheduleMutation();
  const updateScheduleMutation = useUpdateSourceScheduleMutation();
  const deleteScheduleMutation = useDeleteSourceScheduleMutation();

  const {S, lastAge, runSummary} = useRunStream(runId);
  const mrPlanQuery = useMrPlanQuery(runId, 'product-common');
  const mrPlan = mrPlanQuery.data;

  const filteredRuns = useMemo(() => runs.filter(r => selectedSource === 'all' || r.source_id === selectedSource), [runs, selectedSource]);
  const activeRun = runs.find(r => r.run_id === runId);
  const [state] = runState(S, lastAge);
  const live = state === 'running' || state === 'stalled';
  const stages = [...S.stages.values()].filter(s => s.status != null);

  const saveSource = async () => {
    try {
      const existing = sources.some(s => s.id === sourceForm.id);
      const data = await saveSourceMutation.mutateAsync({form: sourceForm, existing});
      pushToast(`소스 저장 완료: ${data.label}`, 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const saveDocTarget = async () => {
    try {
      const id = targetForm.id || 'product-common';
      const existing = docTargets.some(t => t.id === id);
      const data = await saveDocTargetMutation.mutateAsync({form: {...targetForm, id}, existing});
      pushToast(`문서 허브 대상 저장 완료: ${data.label}`, 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const saveInstance = async () => {
    try {
      const existing = !!instanceForm.id;
      const data = await saveInstanceMutation.mutateAsync({form: instanceForm, existing});
      pushToast(`인스턴스 저장 완료: ${data.label || data.id}`, 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const toggleInstanceEnabled = async (inst) => {
    try {
      await saveInstanceMutation.mutateAsync({form: {id: inst.id, enabled: !inst.enabled}, existing: true});
      pushToast(inst.enabled ? `${inst.label || inst.id} 비활성화됨` : `${inst.label || inst.id} 활성화됨`, 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const toggleSourceEnabled = async (source) => {
    try {
      await saveSourceMutation.mutateAsync({form: {id: source.id, enabled: !source.enabled}, existing: true});
      pushToast(source.enabled ? `${source.label} 비활성화됨 (소프트 삭제)` : `${source.label} 활성화됨`, 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const doVerifySource = async (id) => {
    const targetId = id || sourceForm.id;
    if (!targetId) return;
    try {
      const result = await verifySourceMutation.mutateAsync(targetId);
      setVerifyResult(result);
      pushToast(result.verified ? `검증 성공: ${result.name || targetId}` : `검증 실패: ${result.error}`, result.verified ? 'success' : 'error');
    } catch (e) {
      setVerifyResult({verified: false, error: e.message});
      pushToast(e.message, 'error');
    }
  };

  const doTriggerRun = async (sourceId) => {
    try {
      const data = await triggerRunMutation.mutateAsync({sourceId, mode: 'auto'});
      pushToast(`실행 시작: ${data.run_id}`, 'success');
      setRunId(data.run_id);
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const doSubmitMr = async () => {
    if (!runId) return;
    try {
      const data = await submitMrMutation.mutateAsync({runId, target: 'product-common'});
      pushToast(data?.result?.merge_request?.web_url ? 'MR 생성 완료' : 'MR 요청 완료', 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const createSourceSchedule = async (schedule) => {
    if (!sourceDetailId) return;
    try {
      await createScheduleMutation.mutateAsync({sourceId: sourceDetailId, schedule});
      pushToast('스케줄이 추가되었습니다', 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const updateSourceSchedule = async (scheduleId, schedule) => {
    if (!sourceDetailId) return;
    try {
      await updateScheduleMutation.mutateAsync({sourceId: sourceDetailId, scheduleId, schedule});
      pushToast('스케줄이 저장되었습니다', 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const deleteSourceSchedule = async (scheduleId) => {
    if (!sourceDetailId) return;
    try {
      await deleteScheduleMutation.mutateAsync({sourceId: sourceDetailId, scheduleId});
      pushToast('스케줄이 삭제되었습니다', 'success');
    } catch (e) {
      pushToast(e.message, 'error');
    }
  };

  const selectSourceForEdit = (s) => {
    setSourceForm({
      ...s,
      themes: Array.isArray(s.themes) ? s.themes.join(',') : (s.themes || ''),
      schedule_time: s.schedule?.time || '20:00',
      schedule_weekdays: s.schedule?.weekdays || ['mon', 'tue', 'wed', 'thu', 'fri'],
      token: '',
    });
    setVerifyResult(null);
  };

  const goRepositories = () => setPage('repositories');
  const detailSource = sources.find(s => s.id === sourceDetailId);

  return (
    <div className="app">
      <SideNav page={page} onNavigate={setPage} health={health} liveStatus={liveStatus} />
      <main className="main">
        {page === 'home' && <HomePage
          sources={sources}
          dbRuns={dbRuns}
          isLoading={sourcesQuery.isLoading || dbRunsQuery.isLoading}
          isError={sourcesQuery.isError || dbRunsQuery.isError}
          error={sourcesQuery.error || dbRunsQuery.error}
          onRetry={() => { sourcesQuery.refetch(); dbRunsQuery.refetch(); }}
          onOpenWizard={openWizard}
          onSelectRun={setRunId}
          onOpenRepositories={goRepositories}
        />}

        {page === 'repositories' && (sourceDetailId
          ? <SourceDetailPage
            source={detailSource}
            runs={sourceRunsQuery.data || []}
            onBack={closeSourceDetail}
            onSelectRun={setRunId}
            onTrigger={doTriggerRun}
            onVerify={doVerifySource}
            verifyResult={verifyResult}
            editForm={sourceForm}
            onEditFormChange={setSourceForm}
            onSaveEdit={saveSource}
            saveBusy={saveSourceMutation.isPending}
            saveMessage=""
            onCreateSchedule={createSourceSchedule}
            onUpdateSchedule={updateSourceSchedule}
            onDeleteSchedule={deleteSourceSchedule}
            scheduleBusy={createScheduleMutation.isPending || updateScheduleMutation.isPending || deleteScheduleMutation.isPending}
          />
          : <RepositoriesPage
            instances={instances}
            instanceForm={instanceForm}
            onInstanceFormChange={setInstanceForm}
            onSaveInstance={saveInstance}
            onToggleInstanceEnabled={toggleInstanceEnabled}
            sources={sources}
            query={query}
            onQueryChange={setQuery}
            onOpenWizard={openWizard}
            onOpenDetail={(id) => { selectSourceForEdit(sources.find(s => s.id === id) || blankSource); openSourceDetail(id); }}
            onVerifySource={doVerifySource}
            onTriggerSource={doTriggerRun}
            onEditSource={selectSourceForEdit}
            onToggleSourceEnabled={toggleSourceEnabled}
            targetForm={targetForm}
            onTargetFormChange={setTargetForm}
            onSaveTarget={saveDocTarget}
            busy={saveSourceMutation.isPending || saveInstanceMutation.isPending || saveDocTargetMutation.isPending}
            message=""
            isLoading={sourcesQuery.isLoading || instancesQuery.isLoading}
            isError={sourcesQuery.isError || instancesQuery.isError}
            error={sourcesQuery.error || instancesQuery.error}
            onRetry={() => { sourcesQuery.refetch(); instancesQuery.refetch(); }}
          />
        )}

        {page === 'monitor' && <MonitorPage
          runId={runId} setRunId={setRunId} filteredRuns={filteredRuns}
          selectedSource={selectedSource} setSelectedSource={setSelectedSource} sources={sources}
          S={S} live={live} state={state} stages={stages} activeRun={activeRun}
          runSummary={runSummary} mrPlan={mrPlan} mrBusy={submitMrMutation.isPending}
          mrMessage={submitMrMutation.error?.message || (submitMrMutation.data?.result?.merge_request?.web_url ? `MR 생성 완료: ${submitMrMutation.data.result.merge_request.web_url}` : '')}
          onSubmitMr={doSubmitMr}
          monitorView={monitorView} setMonitorView={setMonitorView}
          onOpenRepositories={goRepositories}
        />}

        {page === 'runs' && <RunsPage
          rows={dbRuns} onSelect={setRunId} onTrigger={doTriggerRun} sources={sources}
          isLoading={dbRunsQuery.isLoading} isError={dbRunsQuery.isError} error={dbRunsQuery.error}
          onRetry={() => dbRunsQuery.refetch()}
        />}

        {page === 'costs' && <CostsPage
          costs={costsQuery.data} overview={overviewQuery.data}
          isLoading={costsQuery.isLoading || overviewQuery.isLoading}
          isError={costsQuery.isError || overviewQuery.isError}
          error={costsQuery.error || overviewQuery.error}
          onRetry={() => { costsQuery.refetch(); overviewQuery.refetch(); }}
        />}
      </main>

      {wizardOpen && <SourceWizard
        onClose={closeWizard}
        onCreated={(created) => pushToast(`소스 등록 완료: ${created.label}`, 'success')}
        onTriggerSuggested={doTriggerRun}
      />}

      <Toasts />
    </div>
  );
}
