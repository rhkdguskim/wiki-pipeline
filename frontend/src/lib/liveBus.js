// 아주 작은 pub/sub 버스 — useLiveSocket이 받은 WS 메시지를 useRunStream 등
// 여러 훅에 prop 없이 전달하기 위한 용도. React 상태가 아니라 순수 이벤트 버스다.

const listeners = new Set();

export function onLiveMessage(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function emitLiveMessage(msg) {
  for (const fn of listeners) fn(msg);
}
