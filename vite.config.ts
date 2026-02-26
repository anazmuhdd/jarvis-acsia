import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/suggest': {
        target: 'https://ac.duckduckgo.com',
        changeOrigin: true,
        secure: true,
        // Strip /api/suggest prefix → DDG expects /ac/
        rewrite: (path) => path.replace(/^\/api\/suggest/, '/ac/'),
        configure: (proxy) => {
          // DDG doesn't send CORS headers — inject them into the response
          // so the browser accepts it as a same-origin response
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['access-control-allow-origin'] = '*';
          });
        },
      },
    },
  },
})
