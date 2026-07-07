import {fmtClock, nf} from '../lib/format.js';

const kindLabel = {thinking: '생각', tool_use: '도구', tool_result: '결과', usage: '토큰', llm_retry: '재시도'};

export function feedText(e) {
  const d = e.detail || {};
  const feedback = d.feedback?.body || d.feedback?.title || '';
  if (d.kind === 'thinking') return feedback || d.summary || '';
  if (d.kind === 'tool_use') return `${d.tool} ${JSON.stringify(d.input || {}).slice(0, 90)}`;
  if (d.kind === 'tool_result') return feedback || `${d.ok ? 'ok' : 'ERR'} ${(d.preview || '').slice(0, 120)}`;
  if (d.kind === 'usage') {
    const model = d.model ? ` · ${d.provider || 'llm'}/${d.model}` : '';
    return `in=${nf.format(d.input_tokens || 0)} out=${nf.format(d.output_tokens || 0)} total=${nf.format(d.total_tokens || ((d.input_tokens || 0) + (d.output_tokens || 0)))}${model}`;
  }
  if (d.kind === 'llm_retry') return feedback || `attempt=${d.attempt} ${d.error || ''}`;
  return JSON.stringify(d).slice(0, 120);
}

export {kindLabel};

export function LiveFeed({feed}) {
  if (!feed.length) return <div className="emptyPanel">이벤트 대기 중</div>;
  return <div className="feed">{feed.slice().reverse().map((e, idx) => {
    const d = e.detail || {};
    const err = (d.kind === 'tool_result' && !d.ok) || d.kind === 'llm_retry';
    return <div className="feedRow" key={`${e.ts}-${idx}`}>
      <time>{fmtClock(Date.parse(e.ts))}</time>
      <span className={`kind ${err ? 'err' : ''}`}>{kindLabel[d.kind] || d.kind || '?'}</span>
      <span className="feedStage">{e.stage}</span>
      <span className="feedText">{feedText(e)}</span>
    </div>;
  })}</div>;
}
