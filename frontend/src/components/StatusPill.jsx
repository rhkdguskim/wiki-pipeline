import {AlertTriangle, CheckCircle2, XCircle, AlertCircle, Clock} from 'lucide-react';
import {runStateLabel} from '../lib/format.js';

export function StatusPill({state}) {
  return <span className={`pill ${state}`}>
    {state === 'done' && <CheckCircle2 size={14} />}
    {state === 'failed' && <XCircle size={14} />}
    {state === 'stalled' && <AlertTriangle size={14} />}
    {state === 'running' && <span className="spinner small" />}
    {(state === 'done_with_warnings' || state === 'partial') && <AlertCircle size={14} />}
    {(state === 'stale' || state === 'timeout') && <Clock size={14} />}
    {runStateLabel(state)}
  </span>;
}
