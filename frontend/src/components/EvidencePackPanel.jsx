// EvidencePackPanel — evidence pack + items + unsupported claim list.

export function EvidencePackPanel({pack, onItemClick}) {
  if (!pack) {
    return <div className="empty-state">evidence pack 이 아직 도착하지 않았습니다.</div>;
  }
  if (pack.missing) {
    return <div className="empty-state">evidence pack 이 없습니다 — backend 가 webhook 으로 보내면 표시됩니다.</div>;
  }
  const items = Array.isArray(pack.items) ? pack.items : [];
  return (
    <div className="evidence-pack-panel">
      <div className="evidence-pack-panel__summary">
        <span className="pill pill--muted">Items {pack.item_count || items.length}</span>
        <span className="pill pill--muted">Files {pack.source_file_count || 0}</span>
        <span className="pill pill--muted">Observations {pack.observation_count || 0}</span>
        <span className={`pill pill--${(pack.unsupported_claim_count || 0) > 0 ? 'warning' : 'muted'}`}>
          Unsupported {pack.unsupported_claim_count || 0}
        </span>
        {pack.truncated && <span className="pill pill--warning">truncated</span>}
      </div>
      {items.length === 0 ? (
        <div className="empty-state">items 가 비어 있습니다.</div>
      ) : (
        <table className="evidence-pack-panel__items">
          <thead>
            <tr>
              <th>ID</th><th>Kind</th><th>Title</th><th>Path</th><th>Lines</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id} onClick={() => onItemClick && onItemClick(it)}>
                <td><code>{it.id}</code></td>
                <td><span className="pill pill--muted">{it.kind}</span></td>
                <td>{it.title}</td>
                <td><code>{it.path || '—'}</code></td>
                <td>
                  {it.line_start != null
                    ? `${it.line_start}–${it.line_end ?? it.line_start}`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
