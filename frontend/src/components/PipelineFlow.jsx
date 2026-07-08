import {CheckCircle2, CircleDot, Loader2, XCircle} from 'lucide-react';

/**
 * PipelineFlow — signature element.
 * Stages as connected horizontal nodes with live state, not a flat checklist.
 *
 * Props:
 *   stages: Array<{ key, label, status: 'pending'|'running'|'done'|'failed', dur? }>
 *   meta?: { label, value }[]   // right-side readout (e.g. elapsed, success%)
 */
const STATUS_ORDER = ['done', 'running', 'pending', 'failed'];

export function PipelineFlow({stages = [], meta = []}) {
  if (!stages.length) return null;

  return <section className="pipelineFlow" aria-label="파이프라인 진행">
    <div className="pipelineRail" role="list">
      {stages.map((s, i) => {
        const next = stages[i + 1];
        const linkStatus = linkState(s.status, next?.status);
        const Icon = iconFor(s.status);
        return <span key={s.key} style={{display: 'contents'}}>
          <span className={`pipelineNode ${s.status}`} role="listitem">
            <span className="pipelineNodeDot">
              {s.status === 'running'
                ? <Loader2 size={13} className="spin" />
                : Icon ? <Icon size={13} /> : <CircleDot size={13} />}
            </span>
            <span className="pipelineNodeLabel" title={s.label}>{s.label}</span>
            {s.dur && <span className="pipelineNodeDur">{s.dur}</span>}
          </span>
          {next && <span className={`pipelineLink ${linkStatus}`} aria-hidden="true" />}
        </span>;
      })}
    </div>
    {meta.length > 0 && (
      <div className="pipelineFlowMeta">
        {meta.map((m, i) => <span key={i} style={{display: 'contents'}}>
          <span className="pfLabel">{m.label}</span>
          <span className="pfValue">{m.value}</span>
        </span>)}
      </div>
    )}
  </section>;
}

function iconFor(status) {
  switch (status) {
    case 'done': return CheckCircle2;
    case 'failed': return XCircle;
    case 'pending': return null;
    case 'running': return null;
    default: return null;
  }
}

function linkState(current, next) {
  if (!next) return '';
  if (current === 'done' && next.status === 'done') return 'done';
  if (current === 'done' && next.status === 'running') return 'running';
  return '';
}
