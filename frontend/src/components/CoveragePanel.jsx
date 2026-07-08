// CoveragePanel — manual coverage percentage / threshold / scenario result table.

export function CoveragePanel({coverage}) {
  if (!coverage) {
    return <div className="empty-state">coverage 정보가 없습니다.</div>;
  }
  if (coverage.status === 'not_applicable' || coverage.status == null) {
    return <div className="empty-state">이 run 은 manual pipeline 이 아닙니다 — coverage 가 적용되지 않습니다.</div>;
  }
  const pct = coverage.percentage;
  const threshold = coverage.threshold;
  const reached = coverage.reached || 0;
  const expected = coverage.expected || 0;
  const misses = coverage.misses || [];
  const tone = coverage.status === 'pass' ? 'success'
              : coverage.status === 'warning' ? 'warning'
              : 'danger';
  return (
    <div className="coverage-panel">
      <div className="coverage-panel__summary">
        <span className={`pill pill--${tone}`}>
          {pct != null ? `${pct.toFixed(1)}%` : '—'}
        </span>
        {threshold != null && <span className="pill pill--muted">Threshold {threshold}%</span>}
        <span className="pill pill--muted">Reached {reached}/{expected}</span>
        <span className={`pill pill--${tone}`}>{coverage.status}</span>
      </div>
      {Array.isArray(coverage.scenario_results) && coverage.scenario_results.length > 0 && (
        <>
          <h4>Scenario results</h4>
          <table className="coverage-panel__scenarios">
            <thead>
              <tr><th>Scenario</th><th>Status</th><th>Detail</th></tr>
            </thead>
            <tbody>
              {coverage.scenario_results.map((s, i) => (
                <tr key={i}>
                  <td>{s.id || s.name || `scenario-${i}`}</td>
                  <td>
                    <span className={`pill pill--${s.status === 'pass' ? 'success' : s.status === 'fail' ? 'danger' : 'warning'}`}>
                      {s.status || 'unknown'}
                    </span>
                  </td>
                  <td>{s.detail || s.message || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {misses.length > 0 && (
        <>
          <h4>Missed features</h4>
          <ul className="coverage-panel__misses">
            {misses.map((m, i) => (
              <li key={i}>
                <code>{m.id || m.name || `miss-${i}`}</code>
                {m.reason && <span> — {m.reason}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
