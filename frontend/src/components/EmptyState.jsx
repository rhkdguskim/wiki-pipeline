export function EmptyState({icon: Icon, title, description, actionLabel, onAction}) {
  return <div className="emptyState">
    {Icon && <div className="emptyStateIcon"><Icon size={22} /></div>}
    <strong>{title}</strong>
    {description && <p>{description}</p>}
    {actionLabel && onAction && <button className="primaryBtn" onClick={onAction}>{actionLabel}</button>}
  </div>;
}
