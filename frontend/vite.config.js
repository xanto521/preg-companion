import { fileURLToPath } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'viewer-entry',
      configureServer(server) {
        server.middlewares.use((request, _response, next) => {
          if (/^\/view\/[^/?]+(?:\?.*)?$/.test(request.url || '')) request.url = '/viewer.html'
          next()
        })
      },
    },
  ],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    rollupOptions: {
      input: {
        recorder: fileURLToPath(new URL('./index.html', import.meta.url)),
        viewer: fileURLToPath(new URL('./viewer.html', import.meta.url)),
      },
    },
  },
})
