// Control Plane 자체 토큰 인증 (CONTROL_API_TOKENS 설정 시): localStorage.cp_token을 모든 API 호출에 첨부
export const api = (url, opts = {}) => {
  const token = localStorage.getItem('cp_token');
  const headers = {...(opts.headers || {}), ...(token ? {'X-Api-Token': token} : {})};
  return fetch(url, {...opts, headers});
};

async function asJson(r) {
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || data.detail || `요청 실패 (${r.status})`);
  return data;
}

function jsonBody(payload, method) {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)};
}

export const getSources = () => api('/api/sources').then(asJson);

export const saveSource = (form, existing) =>
  api(existing ? `/api/sources/${encodeURIComponent(form.id)}` : '/api/sources',
    jsonBody(form, existing ? 'PATCH' : 'POST')).then(asJson);

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

export const getDbRuns = (limit = 100) => api(`/api/runs/db?limit=${limit}`).then(asJson);

export const triggerRun = (sourceId, mode = 'auto') =>
  api('/api/runs/trigger', jsonBody({source_id: sourceId, mode}, 'POST')).then(asJson);

export const getRunSummary = runId => api(`/api/run-summary?run=${encodeURIComponent(runId)}`).then(asJson);

export const getEvents = (runId, offset) => api(`/api/events?run=${encodeURIComponent(runId)}&offset=${offset}`).then(asJson);

export const getOverview = () => api('/api/overview').then(asJson);

export const getCosts = () => api('/api/costs').then(asJson);

export const getMrPlan = (runId, target = 'product-common') =>
  api(`/api/docs-hub/mr-plan?run=${encodeURIComponent(runId)}&target=${encodeURIComponent(target)}`).then(asJson);

export const submitMr = (runId, target = 'product-common') =>
  api('/api/docs-hub/submit-mr', jsonBody({run: runId, target, confirm: target}, 'POST')).then(asJson);

export const getHealth = () => api('/health').then(asJson);
