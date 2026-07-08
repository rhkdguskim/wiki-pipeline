// RemoteVncMonitor — mcp-vnc view-only 모니터 placeholder.
// 실제 react-vnc 통합은 dependency 추가 후 진행. v1 은 메타데이터/연결 상태 표시에 집중.

import {useEffect, useRef, useState} from 'react';

export function RemoteVncMonitor({session, runId}) {
  const canvasRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!session?.available || !session?.websocket_url) {
      setConnected(false);
      return;
    }
    // v1: websocket URL 만 보유하고 있어도 view-only 모드면 안전.
    // react-vnc 가 도입되면 이 effect 가 canvas 에 frame 을 그리고
    // input 이벤트는 preventDefault 로 막는다.
    setConnected(false);
    setError('react-vnc 미연결 — v1 은 모니터 메타데이터만 표시');
  }, [session, runId]);

  if (!session) {
    return <div className="empty-state">VNC session 정보가 없습니다.</div>;
  }
  if (!session.available) {
    return (
      <div className="vnc-monitor vnc-monitor--unavailable">
        <span className="pill pill--muted">VNC unavailable</span>
        <p>remote control 환경이 비활성화되어 있거나 mcp-vnc 가 연결되지 않았습니다.</p>
      </div>
    );
  }
  return (
    <div className="vnc-monitor" data-view-only={session.view_only ? 'true' : 'false'}>
      <div className="vnc-monitor__header">
        <span className={`pill pill--${session.view_only ? 'success' : 'danger'}`}>
          {session.view_only ? 'view-only' : 'interactive (blocked)'}
        </span>
        <span className="pill pill--muted">session {session.session_id || '—'}</span>
        <span className="pill pill--muted">host {session.host_label || '—'}:{session.port_label || '—'}</span>
        {session.latency_ms != null && (
          <span className="pill pill--muted">latency {session.latency_ms}ms</span>
        )}
        {session.resolution && (
          <span className="pill pill--muted">{session.resolution}</span>
        )}
      </div>
      <div className="vnc-monitor__scenario">
        <strong>Current step:</strong> {session.current_scenario_step || '—'}
        <br />
        <strong>Action:</strong> {session.current_action || '—'}
      </div>
      <div className="vnc-monitor__canvas-wrap">
        <canvas
          ref={canvasRef}
          width={1920}
          height={1080}
          style={{width: '100%', height: 'auto', maxHeight: '60vh'}}
          tabIndex={-1}
        />
        {!connected && (
          <div className="vnc-monitor__overlay">
            <span>react-vnc dependency 가 없어 live frame 이 표시되지 않습니다.</span>
            <small>websocket_url={session.websocket_url || '—'}</small>
            <small>expires_at={session.expires_at || '—'}</small>
          </div>
        )}
      </div>
      {error && <div className="vnc-monitor__error">{error}</div>}
    </div>
  );
}
