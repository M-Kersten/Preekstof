import { readFileSync } from 'node:fs'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The version this interface was built from, read from the one place it is written. The
// running server says its own; when the two differ, the window was never restarted.
const built = /^VERSION = "([^"]+)"/m.exec(
  readFileSync(new URL('../backend/version.py', import.meta.url), 'utf8'))?.[1] ?? ''

// The API runs on port 8000 (uvicorn backend.main:app); the dev server proxies to it.
const backend = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  define: { __BUILT_VERSION__: JSON.stringify(built) },
  server: {
    // Everything the API answers on. A route missing here fails in dev only, as index.html
    // coming back where JSON was expected, so the list is kept complete on purpose.
    proxy: Object.fromEntries(
      ['/brands', '/church', '/diagnose', '/fonts', '/health', '/kerkdienstgemist', '/logos', '/music',
       '/outro', '/privacy', '/projects', '/selftest', '/services', '/setup', '/share', '/storage',
       '/templates', '/words'].map((path) => [path, backend]),
    ),
  },
})
