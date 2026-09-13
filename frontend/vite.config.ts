import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const backendTarget = env.MORPHEUS_BACKEND_URL || 'http://127.0.0.1:8000'
  const parsedPort = Number.parseInt(env.MORPHEUS_FRONTEND_PORT || '5173', 10)
  const frontendPort = Number.isFinite(parsedPort) ? parsedPort : 5173

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: frontendPort,
      strictPort: true,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: false
        }
      }
    }
  }
})
