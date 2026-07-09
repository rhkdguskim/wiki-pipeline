import react from '@vitejs/plugin-react';
import {defineConfig} from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://110.110.10.70:8420',
        ws: true,   // /api/ws 웹소켓 프록시
      },
      '/health': {
        target: 'http://110.110.10.70:8420',
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
