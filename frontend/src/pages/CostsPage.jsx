import {CostsPanel} from '../components/CostsPanel.jsx';

export function CostsPage({costs, overview}) {
  return <section className="panel">
    <div className="panelHead"><h2>비용</h2></div>
    <CostsPanel costs={costs} overview={overview} />
  </section>;
}
