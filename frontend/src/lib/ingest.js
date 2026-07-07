export const FEED_MAX = 90;

export const emptyState = () => ({
  firstTs: null,
  lastTs: null,
  runStatus: null,
  pipeline: '',
  inTok: 0,
  outTok: 0,
  llmCalls: 0,
  toolCalls: 0,
  toolErr: 0,
  retries: 0,
  stages: new Map(),
  series: [],
  feed: [],
});

export function ingest(S, e) {
  const next = {...S, stages: new Map(S.stages), series: [...S.series], feed: [...S.feed]};
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
