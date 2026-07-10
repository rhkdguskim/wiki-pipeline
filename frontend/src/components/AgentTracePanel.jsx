import {Bot, Brain, CheckCircle2, CircleAlert, RotateCcw, Wrench} from 'lucide-react';
import {fmtClock, nf} from '../lib/format.js';
import {buildAgentTraces} from '../lib/agentTrace.js';

function ActionIcon({kind, failed}) {
  if (failed) return <CircleAlert size={15} />;
  if (kind === 'thinking') return <Brain size={15} />;
  if (kind === 'tool_use') return <Wrench size={15} />;
  if (kind === 'llm_retry') return <RotateCcw size={15} />;
  return <CheckCircle2 size={15} />;
}

export function AgentTracePanel({feed}) {
  const traces = buildAgentTraces(feed);
  if (!traces.length) return <div className="emptyPanel">에이전트 이벤트 대기 중</div>;

  return <div className="agentTraceList" aria-live="polite">
    {traces.map(trace => <article className="agentTrace" key={trace.stage}>
      <header className="agentTraceHead">
        <div className="agentTraceIdentity">
          <Bot size={18} />
          <div>
            <strong>{trace.label}</strong>
            <span className="mono">{trace.stage}</span>
          </div>
        </div>
        <div className="agentTraceMetrics">
          <span title="LLM 호출">LLM {nf.format(trace.llmCalls)}</span>
          <span title="도구 호출">도구 {nf.format(trace.toolCalls)}</span>
          {trace.retries > 0 && <span className="warnText">재시도 {nf.format(trace.retries)}</span>}
          {trace.failedTools > 0 && <span className="errText">실패 {nf.format(trace.failedTools)}</span>}
        </div>
      </header>
      <ol className="agentTraceActions">
        {trace.actions.map((action, index) => <li className={action.failed ? 'failed' : ''} key={`${action.ts}-${index}`}>
          <ActionIcon kind={action.kind} failed={action.failed} />
          <div>
            <div className="agentTraceActionMeta">
              <strong>{action.label}</strong>
              <time>{fmtClock(Date.parse(action.ts))}</time>
            </div>
            {action.text && <p>{action.text}</p>}
            {action.input && <code>{action.input}</code>}
          </div>
        </li>)}
      </ol>
      {(trace.inputTokens > 0 || trace.outputTokens > 0) && <footer>
        토큰 in {nf.format(trace.inputTokens)} / out {nf.format(trace.outputTokens)}
      </footer>}
    </article>)}
  </div>;
}
