import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {
  getSources, saveSource, saveSourceSchedule,
  createSourceSchedule, updateSourceSchedule, deleteSourceSchedule,
  verifySource, preflightSource,
  getInstances, saveInstance,
  getDocTargets, saveDocTarget,
  getRuns, getDbRuns, triggerRun,
  getMrPlan, submitMr,
  getOverview, getPipelineStatus, getCosts, getHealth,
  getHealthReady, getHealthLive, getHealthStartup,
  getAuditRecent,
  getLlmSettings, getRunDoc,
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

// LLM 런타임 설정 (읽기 전용 — .env 기반, 갱신은 재기동 필요).
export function useLlmSettingsQuery() {
  return useQuery({queryKey: ['llm-settings'], queryFn: getLlmSettings, staleTime: 60000});
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
    mutationFn: ({sourceId, mode}) => triggerRun(sourceId, mode),
    onSuccess: () => {
      qc.invalidateQueries({queryKey: ['runs']});
      qc.invalidateQueries({queryKey: ['dbRuns']});
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
