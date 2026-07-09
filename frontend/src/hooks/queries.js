import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {
  getSources, saveSource, deleteSource, saveSourceSchedule,
  createSourceSchedule, updateSourceSchedule, deleteSourceSchedule,
  verifySource, preflightSource,
  getInstances, saveInstance,
  getDocTargets, saveDocTarget,
  getRuns, getDbRuns, triggerRun,
  getMrPlan, submitMr,
  getOverview, getPipelineStatus, getCosts, getHealth,
  getHealthReady, getHealthLive, getHealthStartup,
  getAuditRecent,
  getLlmSettings, updateLlmSettings, resetLlmSettings, testLlmSettings,
  getRunDoc,
  getRunDocs,
  getRunQuality, getRunEvidence, getRunEvidenceItem, getRunCoverage,
  getRunArtifacts, getRunVncSession,
  getManualProfile, saveManualProfile, preflightManualProfile,
  listScenarios, createScenario, updateScenario, deleteScenario,
  activateScenario, lintScenarios, preflightArtifact,
  reapStuckRuns, getQualitySummary,
} from '../api/client.js';
import {useLiveSocketStore} from '../store/liveSocket.js';

// WS가 연결된 동안은 실시간 invalidate에 의존 — 긴 폴링(60s)은 안전망.
// WS가 끊기면 즉시 5s 폴링으로 폴백.
const LONG_MS = 60000;
const SHORT_MS = 5000;
const HEALTH_MS = 30000;

function useRefetchInterval() {
  // WS 상태가 바뀌면 useQuery의 refetchInterval도 함께 갱신됨 (hook 호출 규칙 준수).
  const status = useLiveSocketStore(s => s.status);
  return status === 'connected' ? LONG_MS : SHORT_MS;
}

// ── 서버 상태 조회 (TanStack Query) ──────────────────────────

export function useSourcesQuery() {
  const refetchInterval = useRefetchInterval();
  return useQuery({queryKey: ['sources'], queryFn: getSources, refetchInterval});
}

export function useInstancesQuery() {
  const refetchInterval = useRefetchInterval();
  return useQuery({queryKey: ['instances'], queryFn: getInstances, refetchInterval});
}

export function useDocTargetsQuery() {
  const refetchInterval = useRefetchInterval();
  return useQuery({queryKey: ['docTargets'], queryFn: getDocTargets, refetchInterval});
}

export function useRunsQuery() {
  const refetchInterval = useRefetchInterval();
  return useQuery({queryKey: ['runs'], queryFn: getRuns, refetchInterval});
}

export function useDbRunsQuery(limit = 100) {
  const refetchInterval = useRefetchInterval();
  return useQuery({queryKey: ['dbRuns', 'all', limit], queryFn: () => getDbRuns(limit), refetchInterval});
}

// 소스별 run 히스토리 — 소스 상세 뷰 전용, 파라미터화 키로 캐시 분리
export function useSourceRunsQuery(sourceId, limit = 100) {
  const refetchInterval = useRefetchInterval();
  return useQuery({
    queryKey: ['dbRuns', sourceId],
    queryFn: () => getDbRuns(limit, sourceId),
    enabled: !!sourceId,
    refetchInterval,
  });
}

export function useCostsQuery() {
  const refetchInterval = useRefetchInterval();
  return useQuery({queryKey: ['costs'], queryFn: getCosts, refetchInterval});
}

export function useOverviewQuery() {
  const refetchInterval = useRefetchInterval();
  return useQuery({queryKey: ['overview'], queryFn: getOverview, refetchInterval});
}

// 파이프라인별 상태 — (source × pipeline_id) 단위 집계. WS 연결 시에는 run_status·
// runs_changed 무효화가 자동 리페치를 담당하므로 폴링은 안전망(60s)만.
export function usePipelineStatusQuery(windowHours = 24) {
  const refetchInterval = useRefetchInterval();
  return useQuery({
    queryKey: ['pipelineStatus', windowHours],
    queryFn: () => getPipelineStatus(windowHours),
    refetchInterval,
  });
}

// 헬스 체크는 WS와 무관한 서버 자체 상태 — 일정한 폴링 유지.
export function useHealthQuery() {
  return useQuery({queryKey: ['health'], queryFn: getHealth, refetchInterval: HEALTH_MS});
}

// Deep health (ENT-D) — k8s 컨벤션. ready 만 폴링해 사이드바/헤더에 반영.
// live/startup 은 진단용으로 별도 수동 호출.
export function useHealthReadyQuery() {
  return useQuery({
    queryKey: ['health-ready'],
    queryFn: getHealthReady,
    refetchInterval: HEALTH_MS,
    retry: 1,
  });
}

export function useHealthLiveQuery() {
  return useQuery({
    queryKey: ['health-live'],
    queryFn: getHealthLive,
    refetchInterval: HEALTH_MS,
    retry: 0,
  });
}

// Audit log (ENT-F) — 관리 작업 이력. action/actor 필터.
export function useAuditRecentQuery(params = {}) {
  const refetchInterval = useRefetchInterval();
  return useQuery({
    queryKey: ['audit-recent', params],
    queryFn: () => getAuditRecent(params),
    refetchInterval,
    staleTime: 10000,
  });
}

// LLM 런타임 설정 — DB 저장값은 다음 Data Plane run부터 runner env로 주입된다.
export function useLlmSettingsQuery() {
  return useQuery({queryKey: ['llm-settings'], queryFn: getLlmSettings, staleTime: 60000});
}

export function useUpdateLlmSettingsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => updateLlmSettings(payload),
    onSuccess: () => qc.invalidateQueries({queryKey: ['llm-settings']}),
  });
}

export function useResetLlmSettingsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => resetLlmSettings(),
    onSuccess: () => qc.invalidateQueries({queryKey: ['llm-settings']}),
  });
}

export function useTestLlmConnectionMutation() {
  return useMutation({
    mutationFn: (payload) => testLlmSettings(payload || {}),
  });
}

// run 산출물 문서 원문 (마크다운/머메이드).
export function useRunDocQuery(runId, path, enabled = true) {
  return useQuery({
    queryKey: ['run-doc', runId, path],
    queryFn: () => getRunDoc(runId, path),
    enabled: !!runId && !!path && enabled,
    staleTime: 120000,
  });
}

// run 의 생성된 문서 목록 (DB 기반) — docu-automation · manual-automation 공통.
// run_summary.generated 와 별개로 DB 에서 직접 조회해 항상 최신 상태를 반영.
export function useRunDocsQuery(runId, enabled = true) {
  return useQuery({
    queryKey: ['run-docs', runId],
    queryFn: () => getRunDocs(runId),
    enabled: !!runId && enabled,
    staleTime: 30000,
  });
}

// runSummary / mrPlan은 useRunStream에서 별도 제어(WS run_status 트리거 반영).
// 여기서 정의하지 않는다 — 호출부가 직접 getRunSummary / getMrPlan을 쓴다.

export function useMrPlanQuery(runId, target = 'product-common') {
  const refetchInterval = useRefetchInterval();
  return useQuery({
    queryKey: ['mrPlan', runId, target],
    queryFn: () => getMrPlan(runId, target),
    enabled: !!runId,
    refetchInterval,
  });
}

// ── 뮤테이션 (저장/트리거/검증/제출) ──────────────────────────

export function useSaveSourceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({form, existing}) => saveSource(form, existing),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['sources']});
    },
  });
}

export function useDeleteSourceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => deleteSource(id),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['sources']});
      qc.invalidateQueries({queryKey: ['dbRuns']});
      qc.invalidateQueries({queryKey: ['pipelineStatus']});
    },
  });
}

export function useCreateSourceScheduleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, schedule}) => createSourceSchedule(sourceId, schedule),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['sources']});
    },
  });
}

export function useUpdateSourceScheduleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, scheduleId, schedule}) => updateSourceSchedule(sourceId, scheduleId, schedule),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['sources']});
    },
  });
}

export function useDeleteSourceScheduleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, scheduleId}) => deleteSourceSchedule(sourceId, scheduleId),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['sources']});
    },
  });
}

export function useVerifySourceMutation() {
  return useMutation({mutationFn: id => verifySource(id)});
}

export function usePreflightSourceMutation() {
  return useMutation({mutationFn: payload => preflightSource(payload)});
}

export function useSaveInstanceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({form, existing}) => saveInstance(form, existing),
    onSuccess: () => qc.invalidateQueries({queryKey: ['instances']}),
  });
}

export function useSaveDocTargetMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({form, existing}) => saveDocTarget(form, existing),
    onSuccess: () => qc.invalidateQueries({queryKey: ['docTargets']}),
  });
}

export function useTriggerRunMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, mode, pipeline_id, branch_role, launch}) =>
      triggerRun(sourceId, {mode, pipeline_id, branch_role, launch}),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['runs']});
      qc.invalidateQueries({queryKey: ['dbRuns']});
      qc.invalidateQueries({queryKey: ['pipelineStatus']});
    },
  });
}

export function useSubmitMrMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({runId, target}) => submitMr(runId, target),
    onSuccess: (_data, vars) => qc.invalidateQueries({queryKey: ['mrPlan', vars.runId]}),
  });
}

// ── AI pipeline quality/evidence/coverage/artifacts/vnc queries (2026-07-08) ────

export function useRunQualityQuery(runId, params = {}) {
  return useQuery({
    queryKey: ['runQuality', runId, params],
    queryFn: () => getRunQuality(runId, params),
    enabled: !!runId,
    staleTime: 30000,
  });
}

export function useRunEvidenceQuery(runId, params = {}) {
  return useQuery({
    queryKey: ['runEvidence', runId, params],
    queryFn: () => getRunEvidence(runId, params),
    enabled: !!runId,
    staleTime: 30000,
  });
}

export function useRunEvidenceItemQuery(runId, itemId) {
  return useQuery({
    queryKey: ['runEvidenceItem', runId, itemId],
    queryFn: () => getRunEvidenceItem(runId, itemId),
    enabled: !!runId && !!itemId,
    staleTime: 60000,
  });
}

export function useRunCoverageQuery(runId) {
  return useQuery({
    queryKey: ['runCoverage', runId],
    queryFn: () => getRunCoverage(runId),
    enabled: !!runId,
    staleTime: 30000,
  });
}

export function useRunArtifactsQuery(runId) {
  return useQuery({
    queryKey: ['runArtifacts', runId],
    queryFn: () => getRunArtifacts(runId),
    enabled: !!runId,
    staleTime: 30000,
  });
}

export function useRunVncQuery(runId) {
  return useQuery({
    queryKey: ['runVnc', runId],
    queryFn: () => getRunVncSession(runId),
    enabled: !!runId,
    staleTime: 10000,
  });
}

// ── Manual profile / scenarios / artifact preflight ───────────

export function useManualProfileQuery(sourceId) {
  return useQuery({
    queryKey: ['manualProfile', sourceId],
    queryFn: () => getManualProfile(sourceId),
    enabled: !!sourceId,
    staleTime: 30000,
  });
}

export function useSaveManualProfileMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, payload}) => saveManualProfile(sourceId, payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({queryKey: ['manualProfile', vars.sourceId]});
    },
  });
}

export function usePreflightManualProfileMutation() {
  return useMutation({mutationFn: sourceId => preflightManualProfile(sourceId)});
}

export function useScenariosQuery(sourceId) {
  return useQuery({
    queryKey: ['scenarios', sourceId],
    queryFn: () => listScenarios(sourceId),
    enabled: !!sourceId,
    staleTime: 30000,
  });
}

export function useCreateScenarioMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, payload}) => createScenario(sourceId, payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({queryKey: ['scenarios', vars.sourceId]});
    },
  });
}

export function useUpdateScenarioMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, scenarioId, payload}) =>
      updateScenario(sourceId, scenarioId, payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({queryKey: ['scenarios', vars.sourceId]});
    },
  });
}

export function useDeleteScenarioMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, scenarioId}) => deleteScenario(sourceId, scenarioId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({queryKey: ['scenarios', vars.sourceId]});
    },
  });
}

export function useActivateScenarioMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({sourceId, scenarioId}) => activateScenario(sourceId, scenarioId),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({queryKey: ['scenarios', vars.sourceId]});
    },
  });
}

export function useLintScenariosMutation() {
  return useMutation({mutationFn: ({sourceId, payload}) => lintScenarios(sourceId, payload)});
}

export function usePreflightArtifactMutation() {
  return useMutation({mutationFn: ({sourceId, payload}) => preflightArtifact(sourceId, payload)});
}

export function useReapStuckRunsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => reapStuckRuns(),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['dbRuns']});
      qc.invalidateQueries({queryKey: ['pipelineStatus']});
    },
  });
}

export function useQualitySummaryQuery(windowHours = 168) {
  return useQuery({
    queryKey: ['qualitySummary', windowHours],
    queryFn: () => getQualitySummary(windowHours),
    staleTime: 60000,
  });
}
