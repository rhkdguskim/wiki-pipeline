export function Stat({label, value, hint, icon: Icon}) {
  return (
    <section className="stat">
      <div className="statIcon"><Icon size={16} /></div>
      <div>
        <div className="statLabel">{label}</div>
        <div className="statValue">{value}</div>
        <div className="statHint">{hint || ' '}</div>
      </div>
    </section>
  );
}
