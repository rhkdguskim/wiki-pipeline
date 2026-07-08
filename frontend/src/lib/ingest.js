export const FEED_MAX = 90;

export const emptyState = () => ({
  firstTs: null,
  lastTs: null,
  runStatus: null,
  pipeline: '',
  inTok: 0,
  outTok: 0,
  llmCalls: 0,
  modelUsage: new Map(),
  toolCalls: 0,
  toolErr: 0,
  retries: 0,
  stages: new Map(),
  series: [],
  feed: [],
});

export function stateFromRunSummary(summary) {
  const next = emptyState();
  if (!summary) return next;

  const stageRows = summary.stages || [];
  const firstStageTs = stageRows
    .map(s => Date.parse(s.first_ts || ''))
    .filter(Number.isFinite)
    .sort((a, b) => a - b)[0];
  const startedTs = Date.parse(summary.started_at || '');
  const lastTs = Date.parse(summary.last_event_at || '');

  next.firstTs = Number.isFinite(firstStageTs) ? firstStageTs : (Number.isFinite(startedTs) ? startedTs : null);
  next.lastTs = Number.isFinite(lastTs) ? lastTs : next.firstTs;
  next.runStatus = summary.status || null;
  next.pipeline = summary.pipeline_id || '';
  next.inTok = summary.kpi?.input_tokens || 0;
  next.outTok = summary.kpi?.output_tokens || 0;
  next.llmCalls = summary.kpi?.llm_calls || 0;
  next.toolCalls = summary.kpi?.tool_calls || 0;
  next.toolErr = summary.kpi?.tool_errors || 0;
  next.modelUsage = new Map((summary.usage_by_model || []).map(row => [
    `${row.provider || 'unknown'}::${row.model || 'unknown'}`,
    row,
  ]));
  next.feed = (summary.timeline || []).slice(-FEED_MAX);

  for (const row of stageRows) {
    const first = Date.parse(row.first_ts || '');
    const last = Date.parse(row.last_ts || '');
    next.stages.set(row.name, {
      layer: row.layer,
      firstTs: Number.isFinite(first) ? first : next.firstTs,
      lastTs: Number.isFinite(last) ? last : (Number.isFinite(first) ? first : next.lastTs),
      status: row.status,
      in: row.input_tokens || 0,
      out: row.output_tokens || 0,
      tools: row.tools || 0,
      progress: row.progress || {},
    });
  }

  return next;
}

export function ingest(S, e) {
  const next = {...S, stages: new Map(S.stages), modelUsage: new Map(S.modelUsage || []), series: [...S.series], feed: [...S.feed]};
  const t = Date.parse(e.ts);
  if (!next.firstTs || t < next.firstTs) next.firstTs = t;
  if (!next.lastTs || t > next.lastTs) next.lastTs = t;
  if (e.pipeline_id) next.pipeline = e.pipeline_id;
  const d = e.detail || {};

  if (e.layer === 'run') {
    next.runStatus = e.status;
    return next;
  }

  if (e.layer === 'stage' || e.layer === 'engine_call') {
    const prev = next.stages.get(e.stage);
    const st = prev || {layer: e.layer, firstTs: t, lastTs: t, status: e.status, in: 0, out: 0, tools: 0};
    next.stages.set(e.stage, {...st, lastTs: t, status: e.status});
    return next;
  }

  if (e.layer === 'agent_step') {
    const prev = next.stages.get(e.stage);
    const st = prev || {layer: 'agent_step', firstTs: t, lastTs: t, status: null, in: 0, out: 0, tools: 0};
    const patched = {...st, lastTs: t};
    if (d.kind === 'usage') {
      next.inTok += d.input_tokens || 0;
      next.outTok += d.output_tokens || 0;
      next.llmCalls += 1;
      patched.in += d.input_tokens || 0;
      patched.out += d.output_tokens || 0;
      const modelKey = `${d.provider || 'unknown'}::${d.model || 'unknown'}`;
      const prevModel = next.modelUsage.get(modelKey) || {
        provider: d.provider || 'unknown', model: d.model || 'unknown',
        input_tokens: 0, output_tokens: 0, calls: 0,
      };
      next.modelUsage.set(modelKey, {
        ...prevModel,
        input_tokens: prevModel.input_tokens + (d.input_tokens || 0),
        output_tokens: prevModel.output_tokens + (d.output_tokens || 0),
        calls: prevModel.calls + 1,
      });
      next.series.push({t, in: next.inTok, out: next.outTok});
    } else if (d.kind === 'tool_use') {
      next.toolCalls += 1;
      patched.tools += 1;
    } else if (d.kind === 'tool_result' && !d.ok) {
      next.toolErr += 1;
    } else if (d.kind === 'llm_retry') {
      next.retries += 1;
    }
    next.stages.set(e.stage, patched);
    next.feed.push(e);
    if (next.feed.length > FEED_MAX) next.feed.splice(0, next.feed.length - FEED_MAX);
  }
  return next;
}
