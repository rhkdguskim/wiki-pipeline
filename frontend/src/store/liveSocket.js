import {create} from 'zustand';

// WS 연결 상태 — connected(실시간)면 useRunStream이 이벤트 폴링을 중단하고 WS만 신뢰한다.
export const useLiveSocketStore = create((set) => ({
  status: 'connecting', // connecting | connected | fallback
  setStatus: (status) => set({status}),
}));
