export function PageHeader({title, description, actions}) {
  return <header className="pageHeader">
    <div>
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
    {actions && <div className="panelActions">{actions}</div>}
  </header>;
}
