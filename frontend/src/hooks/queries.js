import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {
  getSources, saveSource, verifySource, preflightSource,
  getInstances, saveInstance,
  getDocTargets, saveDocTarget,
  getRuns, getDbRuns, triggerRun,
  getRunSummary, getMrPlan, submitMr,
  getOverview, getCosts, getHealth,
} from '../api/client.js';

const RUNS_MS = 10000;
const HEALTH_MS = 30000;

// ── 서버 상태 조회 (TanStack Query) ──────────────────────────

export function useSourcesQuery() {
  return useQuery({queryKey: ['sources'], queryFn: getSources, refetchInterval: RUNS_MS});
}

export function useInstancesQuery() {
  return useQuery({queryKey: ['instances'], queryFn: getInstances, refetchInterval: RUNS_MS});
}

export function useDocTargetsQuery() {
  return useQuery({queryKey: ['docTargets'], queryFn: getDocTargets, refetchInterval: RUNS_MS});
}

export function useRunsQuery() {
  return useQuery({queryKey: ['runs'], queryFn: getRuns, refetchInterval: RUNS_MS});
}

export function useDbRunsQuery(limit = 100) {
  return useQuery({queryKey: ['dbRuns', limit], queryFn: () => getDbRuns(limit), refetchInterval: RUNS_MS});
}

export function useCostsQuery() {
  return useQuery({queryKey: ['costs'], queryFn: getCosts, refetchInterval: RUNS_MS});
}

export function useOverviewQuery() {
  return useQuery({queryKey: ['overview'], queryFn: getOverview, refetchInterval: RUNS_MS});
}

export function useHealthQuery() {
  return useQuery({queryKey: ['health'], queryFn: getHealth, refetchInterval: HEALTH_MS});
}

export function useRunSummaryQuery(runId) {
  return useQuery({
    queryKey: ['runSummary', runId],
    queryFn: () => getRunSummary(runId),
    enabled: !!runId,
    refetchInterval: RUNS_MS,
  });
}

export function useMrPlanQuery(runId, target = 'product-common') {
  return useQuery({
    queryKey: ['mrPlan', runId, target],
    queryFn: () => getMrPlan(runId, target),
    enabled: !!runId,
  });
}

// ── 뮤테이션 (저장/트리거/검증/제출) ──────────────────────────

export function useSaveSourceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({form, existing}) => saveSource(form, existing),
    onSuccess: () => qc.invalidateQueries({queryKey: ['sources']}),
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
