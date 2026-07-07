import {AlertTriangle, CheckCircle2, Radio, XCircle} from 'lucide-react';
import {runStateLabel} from '../lib/format.js';

export function StatusPill({state}) {
  const Icon = state === 'done' ? CheckCircle2 : state === 'failed' ? XCircle : state === 'stalled' ? AlertTriangle : Radio;
  return <span className={`pill ${state}`}><Icon size={14} />{runStateLabel(state)}</span>;
}
