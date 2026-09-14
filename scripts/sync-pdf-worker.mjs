import { copyFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Keep the public worker identical to the installed PDF.js API version.
// Fail immediately if the dependency is missing instead of serving a stale worker.
const root = new URL('../', import.meta.url)
mkdirSync(new URL('public/', root), { recursive: true })
copyFileSync(
  fileURLToPath(new URL('node_modules/pdfjs-dist/build/pdf.worker.min.mjs', root)),
  fileURLToPath(new URL('public/pdf-worker.min.mjs', root)),
)
