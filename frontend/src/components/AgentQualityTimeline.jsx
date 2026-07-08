// AgentQualityTimeline — AI agent role 기반 stage timeline.
// 2026-07-08: Evidence Builder / Scope Planner / Draft Writer / Deterministic Verifier /
// Grounding Critic / Repair Writer / Final Packager role 별 표시.

const ROLE_LABELS = {
  evidence_builder: 'Evidence Builder',
  scope_planner: 'Scope Planner',
  draft_writer: 'Draft Writer',
  deterministic_verifier: 'Deterministic Verifier',
  grounding_critic: 'Grounding Critic',
  repair_writer: 'Repair Writer',
  final_packager: 'Final Packager',
  change_classifier: 'Change Classifier',
  static_evidence_collector: 'Static Evidence Collector',
  theme_writer: 'Theme Writer',
  static_critic: 'Static Critic',
  scenario_preflight_agent: 'Scenario Preflight',
  safe_explorer: 'Safe Explorer',
  coverage_assessor: 'Coverage Assessor',
  manual_writer: 'Manual Writer',
  manual_critic: 'Manual Critic',
};

export function AgentQualityTimeline({stages, runSummary}) {
  if (!stages || stages.size === 0) {
    return <div className="empty-state">stage timeline 이 없습니다.</div>;
  }
  const items = Array.from(stages.entries())
    .filter(([name]) => name && !name.startsWith('manual:') && !name.startsWith('theme:'))
    .map(([name, info]) => {
      const lower = name.toLowerCase();
      const matched = Object.keys(ROLE_LABELS).find((k) => lower.includes(k.replace(/_/g, '-')) || lower.includes(k));
      const role = matched ? ROLE_LABELS[matched] : name;
      return {name, role, ...info};
    });
  return (
    <table className="agent-quality-timeline">
      <thead>
        <tr>
          <th>Role</th>
          <th>Status</th>
          <th>Tokens</th>
          <th>Tools</th>
          <th>Window</th>
        </tr>
      </thead>
      <tbody>
        {items.map((it) => {
          const start = it.firstTs || 0;
          const end = it.lastTs || start;
          const dur = end > start ? `${Math.max(0, Math.floor((end - start) / 1000))}s` : '—';
          const tone = it.status === 'done' ? 'success'
                      : it.status === 'failed' ? 'danger'
                      : it.status === 'running' ? 'info' : 'muted';
          return (
            <tr key={it.name}>
              <td>{it.role}</td>
              <td><span className={`pill pill--${tone}`}>{it.status || 'unknown'}</span></td>
              <td>{(it.in || 0) + (it.out || 0) || '—'}</td>
              <td>{it.tools || 0}</td>
              <td>{dur}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
