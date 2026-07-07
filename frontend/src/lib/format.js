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

const ACTIVE_WINDOW_MS = 45000;

// 스테이지의 표시 상태를 단일 기준으로 계산한다. status가 null인 agent_step 전용 스테이지는
// 'idle'로 두지 않는다 — 최근 활동이면 실행 중(스피너), 오래됐으면 완료로 흡수한다.
// 반환: {state: 'done'|'running'|'failed'|'pending', end: 표시에 쓸 종료 시각(ms)}
export function deriveStageState(s, live) {
  if (s.status === 'failed') return {state: 'failed', end: s.lastTs};
  if (s.status === 'done') return {state: 'done', end: s.lastTs};
  const recent = live && Date.now() - s.lastTs < ACTIVE_WINDOW_MS;
  if (s.status === 'running' || (s.status == null && recent)) {
    return {state: 'running', end: live ? Date.now() : s.lastTs};
  }
  if (s.status == null) return {state: 'done', end: s.lastTs};
  return {state: 'pending', end: s.lastTs};
}
