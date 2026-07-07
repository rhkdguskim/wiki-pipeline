import {create} from 'zustand';

// UI 전용 상태(서버 상태 아님) — selectedSource/runId/tab/마법사 열림 여부
export const useUiStore = create((set) => ({
  selectedSource: 'all',
  setSelectedSource: (id) => set({selectedSource: id}),

  runId: '',
  setRunId: (id) => set({runId: id}),

  tab: 'overview',
  setTab: (tab) => set({tab}),

  wizardOpen: false,
  openWizard: () => set({wizardOpen: true}),
  closeWizard: () => set({wizardOpen: false}),
}));
