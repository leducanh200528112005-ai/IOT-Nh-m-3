import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: {
      // Dev: chuyển /api sang backend nhóm 2 để tránh lỗi CORS
      proxy: { '/api': env.VITE_PROXY_TARGET || 'http://localhost:8000' },
    },
  };
});
