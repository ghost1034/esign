import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
const check = process.argv.includes('--check')
const root = process.cwd()
const temp = check ? mkdtempSync(path.join(tmpdir(), 'esign-openapi-')) : path.join(root, 'backend')
const schema = path.join(temp, 'openapi.json')
const types = check ? path.join(temp, 'api-types.ts') : path.join(root, 'lib/api-types.ts')
try {
  execFileSync(path.join(root, 'backend/.venv/bin/python'), ['generate_openapi.py', '--output', schema], { cwd: path.join(root, 'backend'), env: { ...process.env, ENVIRONMENT: 'local', STORAGE_BACKEND: 'local', TASK_BACKEND: 'local' }, stdio: 'inherit' })
  execFileSync(path.join(root, 'node_modules/.bin/openapi-typescript'), [schema, '--output', types], { stdio: 'inherit' })
  if (check) for (const [actual, expected] of [[schema, 'backend/openapi.json'], [types, 'lib/api-types.ts']]) {
    if (readFileSync(actual, 'utf8') !== readFileSync(expected, 'utf8')) throw new Error(`Generated contract drift: ${expected}`)
  }
} finally { if (check) rmSync(temp, { recursive: true, force: true }) }
