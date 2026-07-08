// Change Impact Panel — raw/2026-07-08-frontend-ai-pipeline-improvement-plan §6.1
// 정적 문서화 run 의 변경 영향 — changed files, affected themes, skip reasons, SHA.

import {FileText, GitBranch, Hash} from 'lucide-react';

export function ChangeImpactPanel({summary}) {
  if (!summary) {
    return <div className="empty-state">변경 영향 데이터 없음</div>;
  }
  const files = Array.isArray(summary.changed_files) ? summary.changed_files : [];
  const themes = Array.isArray(summary.affected_themes) ? summary.affected_themes : [];
  const skipped = Array.isArray(summary.skipped_themes) ? summary.skipped_themes : [];
  const fromSha = summary.from_sha || '';
  const toSha = summary.to_sha || '';

  return (
    <div className="change-impact-panel">
      <div className="change-impact-panel__sha">
        <Hash size={14} />
        {fromSha ? <code className="mono">{fromSha.slice(0, 12)}</code> : <span className="muted">—</span>}
        <span> → </span>
        {toSha ? <code className="mono">{toSha.slice(0, 12)}</code> : <span className="muted">—</span>}
      </div>

      <div className="change-impact-panel__files">
        <strong><FileText size={14} /> 변경 파일 ({files.length})</strong>
        {files.length ? (
          <ul>
            {files.slice(0, 20).map((f, i) => <li key={i} className="mono">{f}</li>)}
            {files.length > 20 && <li className="muted">… 외 {files.length - 20}건</li>}
          </ul>
        ) : <span className="muted">변경 파일 없음</span>}
      </div>

      <div className="change-impact-panel__themes">
        <strong><GitBranch size={14} /> 영향 theme ({themes.length})</strong>
        {themes.length ? (
          <ul>
            {themes.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        ) : <span className="muted">영향 theme 없음</span>}
      </div>

      {skipped.length > 0 && (
        <div className="change-impact-panel__skipped">
          <strong>스킵된 theme ({skipped.length})</strong>
          <ul>
            {skipped.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}