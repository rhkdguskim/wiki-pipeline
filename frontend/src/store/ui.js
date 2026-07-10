import {create} from 'zustand';

let toastSeq = 0;
const TOAST_MAX = 5;
const TOAST_TTL_MS = 4500;
const toastTimers = new Map();   // id -> setTimeout handle (cleanup on dismiss)

function clearTimer(id) {
  const t = toastTimers.get(id);
  if (t) {
    clearTimeout(t);
    toastTimers.delete(id);
  }
}

// UI 전용 상태(서버 상태 아님) — 페이지 라우팅/선택/토스트
export const useUiStore = create((set, get) => ({
  // 최상위 페이지: home | repositories | scheduler | pipelines | costs | audit | settings
  page: 'home',
  setPage: (page) => set({page}),

  selectedSource: 'all',
  setSelectedSource: (id) => set({selectedSource: id}),

  runId: '',
  setRunId: (id) => set({runId: id, page: 'pipelines'}),

  // 파이프라인 상세 내부 서브뷰: overview(개요) | stages(스테이지) | feed(트레이스)
  monitorView: 'overview',
  setMonitorView: (monitorView) => set({monitorView}),

  // 에이전트 판단 요약·도구 사용은 실행 관측의 기본 데이터다. 명시적으로 끈 사용자만
  // 이를 제외한다. 원문 사고 과정은 백엔드가 이벤트에 기록하지 않는다.
  // 값은 localStorage 에 보존해서 새로고침 후에도 유지.
  wsVerbose: (() => {
    try { return localStorage.getItem('cp_ws_verbose') !== '0'; } catch { return true; }
  })(),
  setWsVerbose: (v) => {
    try { localStorage.setItem('cp_ws_verbose', v ? '1' : '0'); } catch { /* ignore */ }
    set({wsVerbose: !!v});
  },

  // repositories 페이지 내부 — 소스 상세로 드릴다운 (null이면 목록)
  sourceDetailId: null,
  openSourceDetail: (id) => set({sourceDetailId: id, page: 'repositories'}),
  closeSourceDetail: () => set({sourceDetailId: null}),

  wizardOpen: false,
  openWizard: () => set({wizardOpen: true}),
  closeWizard: () => set({wizardOpen: false}),

  // 토스트 알림 — {id, kind: info|success|error, text}. 최대 TOAST_MAX 건.
  // 같은 텍스트가 연속으로 오면 중복 무시(의미 없는 도배 방지).
  toasts: [],
  pushToast: (text, kind = 'info') => {
    const trimmed = String(text || '').trim();
    if (!trimmed) return;
    const cur = get().toasts;
    // 동일 텍스트가 이미 살아있으면 갱신하지 않고 무시.
    if (cur.some(t => t.text === trimmed && t.kind === kind)) return;
    const id = ++toastSeq;
    const next = [...cur.filter(t => t.text !== trimmed), {id, text: trimmed, kind}];
    // cap 초과 시 가장 오래된 것부터 제거 (FIFO) — 타이머도 정리.
    while (next.length > TOAST_MAX) {
      const dropped = next.shift();
      clearTimer(dropped.id);
    }
    set({toasts: next});
    toastTimers.set(id, setTimeout(() => get().dismissToast(id), TOAST_TTL_MS));
  },
  dismissToast: (id) => {
    clearTimer(id);
    set({toasts: get().toasts.filter(t => t.id !== id)});
  },
}));
