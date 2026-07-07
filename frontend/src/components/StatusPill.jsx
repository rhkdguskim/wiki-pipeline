import {AlertTriangle, CheckCircle2, XCircle} from 'lucide-react';
import {runStateLabel} from '../lib/format.js';

export function StatusPill({state}) {
  return <span className={`pill ${state}`}>
    {state === 'done' && <CheckCircle2 size={14} />}
    {state === 'failed' && <XCircle size={14} />}
    {state === 'stalled' && <AlertTriangle size={14} />}
    {state === 'running' && <span className="spinner small" />}
    {runStateLabel(state)}
  </span>;
}
