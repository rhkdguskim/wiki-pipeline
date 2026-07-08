/**
 * PageHeader — every page entry.
 * Supports an optional `eyebrow` (mono coordinate label, e.g. "RUN-A3F2 · 02:47")
 * and the standard title/description/actions.
 */
export function PageHeader({title, description, eyebrow, actions}) {
  return <header className="pageHeader">
    <div className="pageHeaderCopy">
      {eyebrow && <div className="pageEyebrow">{eyebrow}</div>}
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
    {actions && <div className="panelActions">{actions}</div>}
  </header>;
}
