import {create} from 'zustand';

// WS 연결 상태 — connected(실시간)면 useRunStream이 이벤트 폴링을 중단하고 WS만 신뢰한다.
// 부가 필드는 SideNav/디버깅 용도: 마지막 이벤트·메시지 수·재연결 시도 횟수.
export const useLiveSocketStore = create((set, get) => ({
  status: 'connecting', // connecting | connected | fallback
  lastEventAt: null,     // epoch ms — 마지막으로 WS 메시지 받은 시각
  messageCount: 0,       // WS로 받은 메시지 총수 (재연결 시 0으로 리셋)
  reconnectAttempts: 0,  // 연결 시도 누적 (연결 성공 시 0으로 리셋)
  setStatus: (status) => set((s) => ({
    status,
    // connected로 전환되면 재연결 카운터 초기화. fallback 진입 시 1 증가.
    reconnectAttempts: status === 'connected' ? 0 : s.reconnectAttempts + (status === 'fallback' && s.status !== 'fallback' ? 1 : 0),
  })),
  noteEvent: () => set((s) => ({lastEventAt: Date.now(), messageCount: s.messageCount + 1})),
  bumpReconnect: () => set((s) => ({reconnectAttempts: s.reconnectAttempts + 1})),
}));
