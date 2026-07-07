import {create} from 'zustand';

let toastSeq = 0;

// UI 전용 상태(서버 상태 아님) — 페이지 라우팅/선택/토스트
export const useUiStore = create((set, get) => ({
  // 최상위 페이지: home | repositories | monitor | runs | costs
  page: 'home',
  setPage: (page) => set({page}),

  selectedSource: 'all',
  setSelectedSource: (id) => set({selectedSource: id}),

  runId: '',
  setRunId: (id) => set({runId: id, page: 'monitor'}),

  // monitor 페이지 내부 서브뷰: overview(개요) | stages(스테이지) | feed(트레이스)
  monitorView: 'overview',
  setMonitorView: (monitorView) => set({monitorView}),

  // repositories 페이지 내부 — 소스 상세로 드릴다운 (null이면 목록)
  sourceDetailId: null,
  openSourceDetail: (id) => set({sourceDetailId: id, page: 'repositories'}),
  closeSourceDetail: () => set({sourceDetailId: null}),

  wizardOpen: false,
  openWizard: () => set({wizardOpen: true}),
  closeWizard: () => set({wizardOpen: false}),

  // 토스트 알림 — {id, kind: info|success|error, text}
  toasts: [],
  pushToast: (text, kind = 'info') => {
    const id = ++toastSeq;
    set({toasts: [...get().toasts, {id, text, kind}]});
    setTimeout(() => get().dismissToast(id), 4500);
  },
  dismissToast: (id) => set({toasts: get().toasts.filter(t => t.id !== id)}),
}));
