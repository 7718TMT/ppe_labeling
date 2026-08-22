import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api/v1': backendUrl,
        '/media': backendUrl
      }
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts'
    }
  }
})
