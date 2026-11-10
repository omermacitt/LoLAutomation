import { randomUUID, timingSafeEqual } from 'node:crypto'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'

const methods: Record<string, string[]> = {
  '/api/health': ['GET'], '/api/settings': ['GET', 'PUT'],
  '/api/champion-catalog': ['GET'], '/api/start_automation': ['POST'],
  '/api/stop_automation': ['POST'], '/api/session': ['GET'],
  '/api/automation/config': ['PUT'],
  '/api/runes/editor-catalog': ['GET'], '/api/runes/validate': ['POST'],
}
function localApi(): Plugin {
  const token = randomUUID()
  const origins = new Set(['http://127.0.0.1:5173', 'http://localhost:5173'])
  return {
    name: 'runepilot-local-api',
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const path = request.url?.split('?')[0] ?? ''
        if (!path.startsWith('/api/')) return next()
        if (request.headers.origin && !origins.has(request.headers.origin)) {
          response.writeHead(403).end()
          return
        }
        const allowed = methods[path]
          ?? (/^\/api\/champions\/[1-9]\d*\/(portrait|runes\/recommended|skins(?:\/[1-9]\d*\/artwork)?)$/.test(path) || /^\/api\/runes\/icons\/[1-9]\d*$/.test(path) ? ['GET'] : undefined)
        if (!allowed) { response.writeHead(404).end(); return }
        if (!allowed.includes(request.method ?? '')) { response.writeHead(405, { Allow: allowed.join(', ') }).end(); return }
        if (path === '/api/session') {
          response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }).end(JSON.stringify({ token }))
          return
        }
        if (request.method !== 'GET') {
          const supplied = request.headers['x-runepilot-session']
          if (typeof supplied !== 'string' || Buffer.byteLength(supplied) !== Buffer.byteLength(token)
            || !timingSafeEqual(Buffer.from(supplied), Buffer.from(token))) {
            response.writeHead(403).end()
            return
          }
          if (!request.headers['content-type']?.startsWith('application/json') && path !== '/api/stop_automation') {
            response.writeHead(415).end()
            return
          }
        }
        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), localApi()],
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: {
      '^/api/(health|settings|champion-catalog|start_automation|stop_automation|automation/config|champions/[1-9]\\d*/(portrait|runes/recommended|skins(/[1-9]\\d*/artwork)?)|runes/(editor-catalog|validate|icons/[1-9]\\d*))$': {
        target: 'http://127.0.0.1:8000', rewrite: (path) => path.replace(/^\/api/, ''),
        timeout: 20_000, proxyTimeout: 20_000,
      },
    },
  },
  test: { include: ['src/**/*.test.{ts,tsx}'], environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'], clearMocks: true, restoreMocks: true },
})
