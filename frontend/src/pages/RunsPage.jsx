import {RunsTable} from '../components/RunsTable.jsx';

export function RunsPage({rows, onSelect, onTrigger, sources}) {
  return <section className="panel">
    <div className="panelHead"><h2>운영 이력</h2></div>
    <RunsTable rows={rows} onSelect={onSelect} onTrigger={onTrigger} sources={sources} />
  </section>;
}
