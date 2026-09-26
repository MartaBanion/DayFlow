import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendOrigin =
    process.env.DAYFLOW_BACKEND_ORIGIN ??
    env.DAYFLOW_BACKEND_ORIGIN ??
    'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': backendOrigin,
        '/healthz': backendOrigin,
      },
    },
  }
})
