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
  // runStatus는 백엔드 run status를 그대로 반영 — 모든 터미널/경고 상태를 매핑한다.
  // 처리하지 못한 상태가 빈 fall-through로 'running'으로 표시되는 것을 방지.
  const s = S.runStatus;
  if (s === 'done') return ['done', '완료'];
  if (s === 'done_with_warnings') return ['done_with_warnings', '경고 완료'];
  if (s === 'failed') return ['failed', '실패'];
  if (s === 'failed_quality_gate') return ['failed_quality_gate', '품질 실패'];
  if (s === 'partial') return ['partial', '부분 완료'];
  if (s === 'stale') return ['stale', '지연'];
  if (s === 'timeout') return ['timeout', '시간 초과'];
  if (s === 'cancelled') return ['cancelled', '취소'];
  // running/pending 은 활동 시간으로 stalled 판별
  if (lastAge > STALL_SEC) return ['stalled', '활동 없음'];
  return ['running', '실행 중'];
}

export function runStateLabel(state) {
  return {
    done: '완료', failed: '실패', stalled: '활동 없음', running: '실행 중',
    pending: '대기', idle: '대기',
    done_with_warnings: '경고 완료', failed_quality_gate: '품질 실패',
    partial: '부분 완료', stale: '지연', timeout: '시간 초과', cancelled: '취소',
  }[state] || state;
}

const ACTIVE_WINDOW_MS = 45000;

// 스테이지의 표시 상태를 단일 기준으로 계산한다.
// agent_step 스테이지는 status가 빈 문자열("")로 오는 경우가 많다 —
// 이는 null과 동일하게 취급한다 (완료로 흡수 또는 실행 중 판별).
// 반환: {state: 'done'|'running'|'failed'|'pending', end: 표시에 쓸 종료 시각(ms)}
export function deriveStageState(s, live) {
  if (s.status === 'failed') return {state: 'failed', end: s.lastTs};
  if (s.status === 'done') return {state: 'done', end: s.lastTs};
  // 빈 문자열 status는 null처럼 처리 — agent_step 완료 표시 누락 방지
  const status = s.status || null;
  const recent = live && Date.now() - s.lastTs < ACTIVE_WINDOW_MS;
  if (status === 'running' || (status == null && recent)) {
    return {state: 'running', end: live ? Date.now() : s.lastTs};
  }
  if (status == null) return {state: 'done', end: s.lastTs};
  return {state: 'pending', end: s.lastTs};
}
