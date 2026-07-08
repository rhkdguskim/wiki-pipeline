// MR Readiness Panel — raw/2026-07-08-frontend-ai-pipeline-improvement-plan §6.3
// mr-plan API 의 readiness/quality/included_files/excluded_files/review_checklist
// 를 시각화하고 submit action 에 review_required 인지 blocked 인지를 표시한다.

import {CheckCircle2, AlertTriangle, XCircle, Clock, ChevronDown, ChevronRight} from 'lucide-react';
import {useState} from 'react';

const TONE = {
  ready: 'success', review_required: 'warning', blocked: 'danger',
  not_created: 'muted', stale: 'warning', partial: 'warning', unknown: 'muted',
};
const LABEL = {
  ready: '제출 가능',
  review_required: '검토 후 제출',
  blocked: '차단됨',
  not_created: '미생성',
  stale: '지연됨',
  partial: '부분 완료',
  unknown: '미평가',
};

function readinessBadge(readiness) {
  const tone = TONE[readiness] || 'muted';
  const label = LABEL[readiness] || readiness || 'unknown';
  return {tone, label};
}

export function MrReadinessPanel({plan, onSubmit, busy}) {
  const [expanded, setExpanded] = useState(false);
  if (!plan) {
    return <div className="empty-state">MR plan 데이터 없음 — backend 가 아직 응답하지 않았습니다.</div>;
  }
  const rb = readinessBadge(plan.readiness);
  const summary = plan.quality_summary || {};
  const included = plan.included_files || [];
  const excluded = plan.excluded_files || [];
  const checklist = plan.review_checklist || [];
  const filesIncluded = Array.isArray(included) ? included : [];
  const filesExcluded = Array.isArray(excluded) ? excluded : [];
  const reviewItems = Array.isArray(checklist) ? checklist : [];

  return (
    <div className="mr-readiness-panel">
      <div className="mr-readiness-panel__header">
        <span className={`pill pill--${rb.tone}`} data-testid="mr-readiness">
          {rb.label}
        </span>
        <span className="muted">included {filesIncluded.length} · excluded {filesExcluded.length}</span>
        {plan.can_submit && onSubmit && (
          <button type="button" className="primaryBtn" disabled={busy} onClick={onSubmit}>
            {rb.tone === 'warning' ? 'MR 제출 (검토 필요)' : 'MR 제출'}
          </button>
        )}
      </div>

      {summary.status && (
        <div className="mr-readiness-panel__quality">
          <span className={`pill pill--${summary.status === 'pass' ? 'success' : summary.status === 'fail' ? 'danger' : 'warning'}`}>
            quality: {summary.status}
          </span>
          {summary.score != null && <span className="muted">score {summary.score}</span>}
          {summary.failed_gate && (
            <span className="warn">failed gate: <code>{summary.failed_gate}</code></span>
          )}
          <span className="muted">warnings {summary.warning_count ?? 0} · errors {summary.error_count ?? 0}</span>
        </div>
      )}

      {plan.blocked_reason && (
        <div className="mr-readiness-panel__blocked">
          <AlertTriangle size={14} />
          <span>{plan.blocked_reason}</span>
        </div>
      )}

      {reviewItems.length > 0 && (
        <details className="mr-readiness-panel__checklist">
          <summary>review checklist ({reviewItems.length})</summary>
          <ul>
            {reviewItems.map((it, i) => <li key={i}>{it}</li>)}
          </ul>
        </details>
      )}

      <button type="button" className="mr-readiness-panel__toggle"
              onClick={() => setExpanded(v => !v)}>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        파일 목록 ({filesIncluded.length + filesExcluded.length})
      </button>
      {expanded && (
        <table className="mr-readiness-panel__files">
          <thead>
            <tr><th>path</th><th>quality</th><th>action</th><th>reason</th></tr>
          </thead>
          <tbody>
            {filesIncluded.map(f => (
              <tr key={`i-${f.id || f.path}`}>
                <td className="mono">{f.path}</td>
                <td>{f.quality_status}</td>
                <td>{f.action}</td>
                <td>{f.review_required ? <span className="warn">review</span> : '✓'}</td>
              </tr>
            ))}
            {filesExcluded.map(f => (
              <tr key={`e-${f.id || f.path}`}>
                <td className="mono">{f.path}</td>
                <td><XCircle size={12} /> {f.quality_status}</td>
                <td>{f.action}</td>
                <td className="warn">{f.reason || 'excluded'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}