import {AlertTriangle, CheckCircle2, Info, X} from 'lucide-react';
import {useUiStore} from '../store/ui.js';

const ICONS = {success: CheckCircle2, error: AlertTriangle, info: Info};

export function Toasts() {
  const toasts = useUiStore(s => s.toasts);
  const dismissToast = useUiStore(s => s.dismissToast);
  if (!toasts.length) return null;
  return <div className="toastStack">
    {toasts.map(t => {
      const Icon = ICONS[t.kind] || Info;
      return <div className={`toast ${t.kind}`} key={t.id}>
        <Icon size={15} />
        <span>{t.text}</span>
        <button className="toastClose" onClick={() => dismissToast(t.id)}><X size={13} /></button>
      </div>;
    })}
  </div>;
}
