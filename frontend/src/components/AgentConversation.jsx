import {fmtClock} from '../lib/format.js';
import {feedText, kindLabel} from './LiveFeed.jsx';

export function AgentConversation({feed}) {
  const events = feed.slice(-24);
  if (!events.length) return <div className="conversation emptyPanel">이벤트 대기 중</div>;
  return <div className="conversation">
    {events.map((e, idx) => {
      const d = e.detail || {};
      const role = d.kind === 'tool_use' ? 'tool' : d.kind === 'tool_result' ? 'result' : d.kind === 'usage' ? 'metric' : d.kind === 'llm_retry' ? 'error' : 'agent';
      return <article className={`bubble ${role}`} key={`${e.ts}-${idx}`}>
        <header><span>{kindLabel[d.kind] || d.kind || 'agent'}</span><time>{fmtClock(Date.parse(e.ts))}</time></header>
        <p>{feedText(e)}</p>
        <footer>{e.stage}</footer>
      </article>;
    })}
  </div>;
}
