// VncSessionBadge — VNC session availability/상태를 run summary/list 에서 빠르게 표시.

export function VncSessionBadge({session}) {
  if (!session || !session.available) {
    return <span className="pill pill--muted">VNC off</span>;
  }
  const tone = session.status === 'connected' ? 'success'
              : session.status === 'connecting' ? 'info'
              : session.status === 'expired' || session.status === 'error' ? 'danger'
              : 'warning';
  return (
    <span className={`pill pill--${tone}`} title={`session ${session.session_id || ''}`}>
      VNC {session.status || 'connecting'}
      {session.view_only ? ' (view-only)' : ''}
    </span>
  );
}
