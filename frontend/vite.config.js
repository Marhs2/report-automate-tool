import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
// 내부망 http 주소에서는 브라우저가 마이크를 막는다. 자체 서명 https로 연다.
import basicSsl from '@vitejs/plugin-basic-ssl'

export default defineConfig({
  plugins: [vue(), basicSsl()],
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
