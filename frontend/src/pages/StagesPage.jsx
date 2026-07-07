import {StageTable} from '../components/StageTable.jsx';

export function StagesPage({S, live}) {
  return <section className="panel"><div className="panelHead"><h2>스테이지 진행</h2></div><StageTable S={S} live={live} /></section>;
}
