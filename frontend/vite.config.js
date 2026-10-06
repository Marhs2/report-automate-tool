import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true, // 회의 녹음 스트림(/meeting/stream)
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
