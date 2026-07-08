import {createRoot} from 'react-dom/client';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {App} from './App.jsx';
import {setAuthErrorHandler} from './api/client.js';
import {useUiStore} from './store/ui.js';
import './styles.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// 401 감지 시 toast로 안내. pushToast는 zustand 어디서든 호출 가능 (React 컴포넌트 밖도 OK).
setAuthErrorHandler(() => {
  useUiStore.getState().pushToast('인증 토큰을 확인하세요 — 좌측 하단 토큰 설정', 'error');
});

createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
);
