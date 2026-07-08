// RunQualityBadge — quality.status / publishable / failedGate 표시.
// 2026-07-08: done_with_warnings / failed_quality_gate 등 새 status 명시 지원.

import {qualityBadge, publishStateBadge, statusBadge} from '../lib/ingest.js';

export function RunQualityBadge({summary, compact = false}) {
  if (!summary) return null;
  const runBadge = statusBadge(summary.status);
  const q = summary.quality || {};
  const qBadge = qualityBadge(q);
  const pBadge = publishStateBadge(summary.publish_state);
  return (
    <div className="run-quality-badge" data-tone={qBadge.tone}>
      <div className="run-quality-badge__row">
        <span className={`pill pill--${runBadge.tone}`}>{runBadge.label}</span>
        <span className={`pill pill--${qBadge.tone}`} data-testid="quality-status">
          {qBadge.label}
        </span>
        {q.score != null && !compact && (
          <span className="pill pill--muted">Score {q.score}</span>
        )}
        <span className={`pill pill--${pBadge.tone}`} data-testid="publish-state">
          {pBadge.label}
        </span>
      </div>
      {q.failed_gate && (
        <div className="run-quality-badge__reason">
          Failed gate: <code>{q.failed_gate}</code>
        </div>
      )}
      {summary.blocked_reason && (
        <div className="run-quality-badge__reason">
          {summary.blocked_reason}
        </div>
      )}
    </div>
  );
}
