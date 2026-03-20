import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/skill.md': 'http://localhost:8080',
      '/skill.json': 'http://localhost:8080',
      '/heartbeat.md': 'http://localhost:8080',
      '/scripts': 'http://localhost:8080',
    },
  },
})
