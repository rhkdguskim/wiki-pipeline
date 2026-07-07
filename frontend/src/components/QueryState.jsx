import {Loader2, RefreshCw} from 'lucide-react';

export function LoadingBlock({label = '불러오는 중…'}) {
  return <div className="loadingBlock"><Loader2 size={18} className="spin" /><span>{label}</span></div>;
}

export function ErrorBanner({message, onRetry}) {
  return <div className="errorBanner">
    <span>불러오지 못했습니다{message ? `: ${message}` : ''}</span>
    {onRetry && <button className="iconTextBtn" onClick={onRetry}><RefreshCw size={13} />재시도</button>}
  </div>;
}
