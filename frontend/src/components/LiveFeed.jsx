import {fmtClock, nf} from '../lib/format.js';

const kindLabel = {
  thinking: '판단', tool_use: '도구', tool_result: '결과', usage: '토큰', llm_retry: '재시도',
  quality_gate_completed: '품질게이트', quality_gate_failed: '품질실패',
  evidence_collected: '근거', evidence_unsupported_claim: '근거부족',
  coverage_updated: '커버리지',
  artifact_selected: '산출물', artifact_deploy_completed: '배포', artifact_build_completed: '빌드',
  mr_plan_ready: 'MR준비', mr_blocked: 'MR차단',
};

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
  // 품질/근거/커버리지/산출물/MR 이벤트는 메시지 필드 우선, 없으면 요약
  if (d.message) return d.message;
  if (d.kind === 'quality_gate_completed' || d.kind === 'quality_gate_failed') {
    return `status=${d.status || '?'} score=${d.score ?? '-'} warnings=${d.warning_count ?? 0} errors=${d.error_count ?? 0}`;
  }
  if (d.kind === 'evidence_collected') return `items=${d.item_count ?? 0}`;
  if (d.kind === 'coverage_updated') return `pct=${d.percentage ?? '-'}% status=${d.status || '?'}`;
  if (d.kind === 'artifact_selected') return `tag=${d.release_tag || '-'} ver=${d.installed_version || '-'}`;
  if (d.kind === 'mr_plan_ready' || d.kind === 'mr_blocked') return d.blocked_reason || 'plan ready';
  // kind 없는 agent_step 이벤트 — error/message/summary 순으로 fallback
  if (d.error) return String(d.error).slice(0, 120);
  if (d.summary) return d.summary;
  return JSON.stringify(d).slice(0, 120);
}

export {kindLabel};

export function LiveFeed({feed}) {
  if (!feed.length) return <div className="emptyPanel">이벤트 대기 중</div>;
  return <div className="feed">{feed.slice().reverse().map((e, idx) => {
    const d = e.detail || {};
    const err = (d.kind === 'tool_result' && !d.ok) || d.kind === 'llm_retry';
    const kind = d.kind || 'event';
    return <div className="feedRow" key={`${e.ts}-${idx}`}>
      <time>{fmtClock(Date.parse(e.ts))}</time>
      <span className={`kind ${err ? 'err' : ''}`}>{kindLabel[kind] || kind}</span>
      <span className="feedStage">{e.stage || '—'}</span>
      <span className="feedText">{feedText(e)}</span>
    </div>;
  })}</div>;
}
