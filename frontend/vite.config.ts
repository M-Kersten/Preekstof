import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The version this interface was built from, read from the one place it is written. The
// running server says its own; when the two differ, the window was never restarted.
const built = /^VERSION = "([^"]+)"/m.exec(
  readFileSync(new URL('../backend/version.py', import.meta.url), 'utf8'))?.[1] ?? ''

// Between releases the number stays put while the code moves, so the files that decide what
// the server answers are fingerprinted too, the same way backend/version.py does it.
const fingerprint = createHash('sha256')
for (const name of ['models.py', 'main.py']) {
  fingerprint.update(readFileSync(new URL(`../backend/${name}`, import.meta.url), 'utf8').replace(/\r\n/g, '\n'))
}
const builtFrom = fingerprint.digest('hex').slice(0, 12)

// The API runs on port 8000 (uvicorn backend.main:app); the dev server proxies to it.
const backend = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  define: { __BUILT_VERSION__: JSON.stringify(built), __BUILT_FROM__: JSON.stringify(builtFrom) },
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
