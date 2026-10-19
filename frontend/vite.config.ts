import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({mode}) => ({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': loadEnv(mode, '.', 'LEXITRACE_').LEXITRACE_API_TARGET || 'http://localhost:8000',
      '/predict': loadEnv(mode, '.', 'LEXITRACE_').LEXITRACE_API_TARGET || 'http://localhost:8000'
    }
  }
}));
