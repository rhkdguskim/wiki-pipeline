const ROLE_LABELS = {
  search: '탐색',
  compose: '요약 합성',
  write: '문서 작성',
  writer: '문서 작성',
  critic: '품질 검토',
  chunked: '세부 검토',
  explore: '화면 탐색',
  traversal: '시나리오 순회',
};

const ACTION_LABELS = {
  thinking: '판단 요약',
  tool_use: '도구 호출',
  tool_result: '도구 결과',
  usage: 'LLM 사용량',
  llm_retry: 'LLM 재시도',
};

function stringify(value) {
  try {
    return JSON.stringify(value || {});
  } catch {
    return '{}';
  }
}

function actionText(detail) {
  const feedback = detail.feedback?.body || detail.feedback?.title || '';
  if (detail.kind === 'thinking') return feedback || detail.summary || '';
  if (detail.kind === 'tool_use') return detail.tool || '도구';
  if (detail.kind === 'tool_result') return feedback || detail.preview || '';
  if (detail.kind === 'usage') return `in ${detail.input_tokens || 0} / out ${detail.output_tokens || 0}`;
  if (detail.kind === 'llm_retry') return detail.error || `시도 ${detail.attempt || '?'}`;
  return feedback || detail.summary || detail.message || '';
}

export function agentLabel(stage = '') {
  const [role, ...target] = String(stage || 'agent').split(':');
  const label = ROLE_LABELS[role] || role || '에이전트';
  return target.length ? `${label} · ${target.join(':')}` : label;
}

export function buildAgentTraces(feed = []) {
  const byStage = new Map();
  for (const event of feed) {
    if (event?.layer !== 'agent_step') continue;
    const stage = event.stage || 'agent';
    let trace = byStage.get(stage);
    if (!trace) {
      trace = {
        stage,
        label: agentLabel(stage),
        firstTs: event.ts || '',
        lastTs: event.ts || '',
        toolCalls: 0,
        failedTools: 0,
        retries: 0,
        llmCalls: 0,
        inputTokens: 0,
        outputTokens: 0,
        actions: [],
      };
      byStage.set(stage, trace);
    }
    const detail = event.detail || {};
    const kind = detail.kind || 'event';
    trace.lastTs = event.ts || trace.lastTs;
    if (kind === 'tool_use') trace.toolCalls += 1;
    if (kind === 'tool_result' && !detail.ok) trace.failedTools += 1;
    if (kind === 'llm_retry') trace.retries += 1;
    if (kind === 'usage') {
      trace.llmCalls += 1;
      trace.inputTokens += detail.input_tokens || 0;
      trace.outputTokens += detail.output_tokens || 0;
    }
    trace.actions.push({
      kind,
      label: ACTION_LABELS[kind] || kind,
      text: actionText(detail),
      input: kind === 'tool_use' ? stringify(detail.input).slice(0, 220) : '',
      failed: (kind === 'tool_result' && !detail.ok) || kind === 'llm_retry',
      ts: event.ts || '',
    });
  }
  return [...byStage.values()].sort((a, b) => String(b.lastTs).localeCompare(String(a.lastTs)));
}
