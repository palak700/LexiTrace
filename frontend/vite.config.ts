import {defineConfig, loadEnv} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({mode})=>{
  const env={...loadEnv(mode,'..','LEXITRACE_'),...loadEnv(mode,'../backend','LEXITRACE_'),...loadEnv(mode,'.','LEXITRACE_'),...process.env};
  const target=env.LEXITRACE_API_TARGET||`http://127.0.0.1:${env.LEXITRACE_BACKEND_PORT||'8000'}`;
  return {plugins:[react()],server:{port:5173,proxy:{'/api':target,'/predict':target,'/evaluate':target}}};
});
