// QualityGatePanel — quality report + findings + repair loop timeline.
// 2026-07-08: gate 별 pass/warning/fail + blocking findings + repair status.

export function QualityGatePanel({quality, findings = []}) {
  if (!quality) {
    return (
      <div className="empty-state">
        품질 평가가 아직 진행되지 않았습니다 — backend 가 webhook 을 보내면 여기에 표시됩니다.
      </div>
    );
  }
  const gates = Array.isArray(quality.gates) ? quality.gates : [];
  return (
    <div className="quality-gate-panel">
      <div className="quality-gate-panel__summary">
        <span className={`pill pill--${quality.status === 'pass' ? 'success' : quality.status === 'warning' ? 'warning' : quality.status === 'fail' ? 'danger' : 'muted'}`}>
          {quality.status || 'not_evaluated'}
        </span>
        {quality.score != null && <span className="pill pill--muted">Score {quality.score}</span>}
        <span className="pill pill--muted">Warnings {quality.warning_count || 0}</span>
        <span className="pill pill--muted">Errors {quality.error_count || 0}</span>
        <span className="pill pill--muted">Repair attempts {quality.repair_attempts || 0}</span>
      </div>
      {quality.failed_gate && (
        <div className="quality-gate-panel__failed">
          <strong>Failed gate:</strong> <code>{quality.failed_gate}</code>
        </div>
      )}
      {gates.length > 0 && (
        <table className="quality-gate-panel__gates">
          <thead>
            <tr><th>Gate</th><th>Status</th><th>Detail</th></tr>
          </thead>
          <tbody>
            {gates.map((g, i) => (
              <tr key={i}>
                <td>{g.name || g.gate || `gate-${i}`}</td>
                <td>
                  <span className={`pill pill--${g.status === 'pass' ? 'success' : g.status === 'fail' ? 'danger' : 'warning'}`}>
                    {g.status || 'unknown'}
                  </span>
                </td>
                <td>{g.detail || g.message || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h4>Findings</h4>
      {findings.length === 0 ? (
        <div className="empty-state">표시할 finding 이 없습니다.</div>
      ) : (
        <ul className="quality-gate-panel__findings">
          {findings.map((f, i) => (
            <li key={i} className={f.blocking ? 'finding finding--blocking' : 'finding'}>
              <div>
                <span className={`pill pill--${f.severity === 'blocker' || f.severity === 'error' ? 'danger' : 'warning'}`}>
                  {f.severity}
                </span>
                {f.blocking && <span className="pill pill--danger">blocking</span>}
                <code className="finding__code">{f.code}</code>
              </div>
              <div className="finding__message">{f.message}</div>
              {f.location && <div className="finding__location">in {f.location}</div>}
              {f.evidence_ref && <div className="finding__evidence">evidence: {f.evidence_ref}</div>}
              {f.repair_status && <div className="finding__repair">repair: {f.repair_status}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
