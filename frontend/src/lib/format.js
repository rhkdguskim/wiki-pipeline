export const STALL_SEC = 90;

export const nf = new Intl.NumberFormat('en-US');
export const compact = new Intl.NumberFormat('en-US', {notation: 'compact', maximumFractionDigits: 1});

export function fmtNum(n) {
  return n >= 10000 ? compact.format(n) : nf.format(n);
}

export function fmtDur(ms) {
  if (ms == null || ms < 0) return '-';
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, '0');
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`;
}

export function fmtClock(t) {
  return t ? new Date(t).toTimeString().slice(0, 8) : '-';
}

export function runState(S, lastAge) {
  if (S.runStatus === 'done') return ['done', '완료'];
  if (S.runStatus === 'failed') return ['failed', '실패'];
  if (lastAge > STALL_SEC) return ['stalled', '활동 없음'];
  return ['running', '실행 중'];
}

export function runStateLabel(state) {
  return {done: '완료', failed: '실패', stalled: '활동 없음', running: '실행 중'}[state] || state;
}
