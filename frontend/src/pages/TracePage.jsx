import {LiveFeed} from '../components/LiveFeed.jsx';

export function TracePage({feed}) {
  return <section className="panel"><div className="panelHead"><h2>에이전트 라이브 피드</h2></div><LiveFeed feed={feed} /></section>;
}
