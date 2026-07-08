// Control Plane 자체 토큰 인증 (CONTROL_API_TOKENS 설정 시):
// localStorage.cp_token을 모든 API 호출에 첨부.
// 401 응답은 친절한 에러로 정규화 — 설정 > 인증에서 토큰을 다시 입력하도록 안내.
const AUTH_ERROR_HINT = '인증 토큰이 유효하지 않습니다. 설정 > 인증에서 API 토큰을 확인하세요.';
// ENT-E rate limit. 429 + Retry-After 헤더는 호출자가 보고용으로 쓸 수 있게
// 일반화 — asJson 이 throw 하기 전에 콜백을 한 번 부른다.
let rateLimitHandler = null;
export function setRateLimitHandler(fn) { rateLimitHandler = fn; }

export const api = (url, opts = {}) => {
  const token = localStorage.getItem('cp_token');
  const headers = {...(opts.headers || {}), ...(token ? {'X-Api-Token': token} : {})};
  return fetch(url, {...opts, headers});
};

// 401 감지 시 호출부에 안내 메시지를 전달하고, 선택적으로 콜백을 실행한다.
// 다른 곳(useLiveSocket, App.jsx)에서 onAuthError 콜백을 등록해 UI 반응(toast 등)을 담당한다.
let authErrorHandler = null;
export function setAuthErrorHandler(fn) { authErrorHandler = fn; }

async function asJson(r) {
  const raw = await r.text();
  let data = null;
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      throw new Error(r.ok ? '응답을 해석할 수 없습니다 (JSON 아님)' : `요청 실패 (${r.status})`);
    }
  }
  if (r.status === 401) {
    if (authErrorHandler) authErrorHandler();
    throw new Error(data?.error || data?.detail || AUTH_ERROR_HINT);
  }
  if (r.status === 429) {
    // Retry-After 헤더(초) 가 있으면 그만큼, 없으면 detail.retry_after_sec 사용.
    const retryAfter = Number(r.headers.get('Retry-After') || 0)
      || (data && (data.retry_after_sec || data.detail?.retry_after_sec))
      || 60;
    if (rateLimitHandler) {
      try { rateLimitHandler({retryAfter, message: data?.error || data?.detail}); } catch (e) { /* ignore */ }
    }
    throw new Error(`분당 요청 한도 초과 — ${Math.ceil(retryAfter)}초 후 다시 시도`);
  }
  if (!r.ok) throw new Error(data?.error || data?.detail || `요청 실패 (${r.status})`);
  return data;
}

function jsonBody(payload, method) {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)};
}

export const getSources = () => api('/api/sources').then(asJson);

export const saveSource = (form, existing) =>
  api(existing ? `/api/sources/${encodeURIComponent(form.id)}` : '/api/sources',
    jsonBody(form, existing ? 'PATCH' : 'POST')).then(asJson);

export const deleteSource = id =>
  api(`/api/sources/${encodeURIComponent(id)}`, {method: 'DELETE'}).then(asJson);

export const saveSourceSchedule = (sourceId, schedule) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/schedule`, jsonBody(schedule, 'PATCH')).then(asJson);

export const createSourceSchedule = (sourceId, schedule) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/schedules`, jsonBody(schedule, 'POST')).then(asJson);

export const updateSourceSchedule = (sourceId, scheduleId, schedule) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/schedules/${encodeURIComponent(scheduleId)}`, jsonBody(schedule, 'PATCH')).then(asJson);

export const deleteSourceSchedule = (sourceId, scheduleId) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/schedules/${encodeURIComponent(scheduleId)}`, {method: 'DELETE'}).then(asJson);

export const verifySource = id => api(`/api/sources/${encodeURIComponent(id)}/verify`, {method: 'POST'}).then(asJson);

export const preflightSource = payload => api('/api/sources/preflight', jsonBody(payload, 'POST')).then(asJson);

export const getInstances = () => api('/api/instances').then(asJson);

export const saveInstance = (form, existing) =>
  api(existing ? `/api/instances/${encodeURIComponent(form.id)}` : '/api/instances',
    jsonBody(form, existing ? 'PATCH' : 'POST')).then(asJson);

export const getDocTargets = () => api('/api/docs-hub').then(asJson);

export const saveDocTarget = (form, existing) =>
  api(existing ? `/api/docs-hub/${encodeURIComponent(form.id)}` : '/api/docs-hub',
    jsonBody(form, existing ? 'PATCH' : 'POST')).then(asJson);

export const getRuns = () => api('/api/runs').then(asJson);

export const getDbRuns = (limit = 100, sourceId = '') =>
  api(`/api/runs/db?limit=${limit}${sourceId ? `&source=${encodeURIComponent(sourceId)}` : ''}`).then(asJson);

export const triggerRun = (sourceId, mode = 'auto') =>
  api('/api/runs/trigger', jsonBody({source_id: sourceId, mode}, 'POST')).then(asJson);

export const getRunSummary = runId => api(`/api/run-summary?run=${encodeURIComponent(runId)}`).then(asJson);

export const getEvents = (runId, offset) => api(`/api/events?run=${encodeURIComponent(runId)}&offset=${offset}`).then(asJson);

export const getRunEventsSeq = (runId, afterSeq = 0, limit = 500) =>
  api(`/api/runs/${encodeURIComponent(runId)}/events?afterSeq=${afterSeq}&limit=${limit}`).then(asJson);

export const getRunQuality = (runId, params = {}) => {
  const qs = new URLSearchParams();
  if (params.severity) qs.set('severity', params.severity);
  if (params.blocking != null) qs.set('blocking', String(params.blocking));
  if (params.doc_id) qs.set('doc_id', params.doc_id);
  const tail = qs.toString();
  return api(`/api/runs/${encodeURIComponent(runId)}/quality${tail ? `?${tail}` : ''}`).then(asJson);
};

export const getRunEvidence = (runId, params = {}) => {
  const qs = new URLSearchParams();
  if (params.kind) qs.set('kind', params.kind);
  if (params.doc_id) qs.set('doc_id', params.doc_id);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.cursor) qs.set('cursor', params.cursor);
  const tail = qs.toString();
  return api(`/api/runs/${encodeURIComponent(runId)}/evidence${tail ? `?${tail}` : ''}`).then(asJson);
};

export const getRunEvidenceItem = (runId, itemId) =>
  api(`/api/runs/${encodeURIComponent(runId)}/evidence/${encodeURIComponent(itemId)}`).then(asJson);

export const getRunCoverage = runId =>
  api(`/api/runs/${encodeURIComponent(runId)}/coverage`).then(asJson);

export const getRunArtifacts = runId =>
  api(`/api/runs/${encodeURIComponent(runId)}/artifacts`).then(asJson);

export const getRunVncSession = runId =>
  api(`/api/runs/${encodeURIComponent(runId)}/vnc-session`).then(asJson);

export const getManualProfile = sourceId =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/manual-profile`).then(asJson);

export const saveManualProfile = (sourceId, payload) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/manual-profile`,
    jsonBody(payload, 'PUT')).then(asJson);

export const preflightManualProfile = sourceId =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/manual-profile/preflight`,
    {method: 'POST'}).then(asJson);

export const listScenarios = sourceId =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/scenarios`).then(asJson);

export const createScenario = (sourceId, payload) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/scenarios`,
    jsonBody(payload, 'POST')).then(asJson);

export const updateScenario = (sourceId, scenarioId, payload) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/scenarios/${encodeURIComponent(scenarioId)}`,
    jsonBody(payload, 'PUT')).then(asJson);

export const deleteScenario = (sourceId, scenarioId) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/scenarios/${encodeURIComponent(scenarioId)}`,
    {method: 'DELETE'}).then(asJson);

export const activateScenario = (sourceId, scenarioId) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/scenarios/${encodeURIComponent(scenarioId)}/activate`,
    {method: 'POST'}).then(asJson);

export const lintScenarios = (sourceId, payload) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/scenarios/lint`,
    jsonBody(payload, 'POST')).then(asJson);

export const preflightArtifact = (sourceId, payload) =>
  api(`/api/sources/${encodeURIComponent(sourceId)}/artifacts/preflight`,
    jsonBody(payload, 'POST')).then(asJson);

export const reapStuckRuns = () =>
  api('/api/internal/reap-stuck', {method: 'POST'}).then(asJson);

export const getQualitySummary = (window = 168) =>
  api(`/api/quality/summary?window=${window}`).then(asJson);

export const getOverview = () => api('/api/overview').then(asJson);

export const getPipelineStatus = (windowHours = 24) =>
  api(`/api/pipelines/status?window=${windowHours}`).then(asJson);

export const getCosts = () => api('/api/costs').then(asJson);

export const getMrPlan = (runId, target = 'product-common') =>
  api(`/api/docs-hub/mr-plan?run=${encodeURIComponent(runId)}&target=${encodeURIComponent(target)}`).then(asJson);

export const submitMr = (runId, target = 'product-common') =>
  api('/api/docs-hub/submit-mr', jsonBody({run: runId, target, confirm: target}, 'POST')).then(asJson);

export const getHealth = () => api('/health').then(asJson);

// Deep health (ENT-D): liveness/ready/startup 분리. k8s 컨벤션이지만
// 프런트 헤더의 서버 상태 표시도 ready 를 보고 'degraded' 표시를 결정한다.
export const getHealthLive = () => api('/health/live').then(asJson);
export const getHealthReady = () => api('/health/ready').then(asJson);
export const getHealthStartup = () => api('/health/startup').then(asJson);

export const getLlmSettings = () => api('/api/settings/llm').then(asJson);

export const updateLlmSettings = (payload) =>
  api('/api/settings/llm', jsonBody(payload, 'PATCH')).then(asJson);

export const resetLlmSettings = () =>
  api('/api/settings/llm', {method: 'DELETE'}).then(asJson);

export const testLlmSettings = (payload = {}) =>
  api('/api/settings/llm/test', jsonBody(payload || {}, 'POST')).then(asJson);

export const getRunDoc = (runId, path) =>
  api(`/api/runs/${encodeURIComponent(runId)}/doc?path=${encodeURIComponent(path)}`).then(asJson);

// Audit log (ENT-F) — 관리 작업 이력 조회. action/actor 필터 지원.
export const getAuditRecent = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.limit) qs.set('limit', params.limit);
  if (params.action) qs.set('action', params.action);
  if (params.actor) qs.set('actor', params.actor);
  const tail = qs.toString();
  return api(`/api/audit/recent${tail ? `?${tail}` : ''}`).then(asJson);
};
