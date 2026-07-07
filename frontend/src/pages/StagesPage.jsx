import {StageChecklist} from '../components/StageChecklist.jsx';

export function StagesPage({S, live}) {
  return <section className="panel"><div className="panelHead"><h2>진행 단계</h2></div><StageChecklist S={S} live={live} /></section>;
}
