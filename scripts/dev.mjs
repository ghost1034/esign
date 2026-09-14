import { spawn, execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
const root = process.cwd()
if (existsSync('.env')) process.loadEnvFile('.env')
const env = { ENVIRONMENT: 'local', DATABASE_URL: 'postgresql://esign:esign@127.0.0.1:55432/esign_dev', STORAGE_BACKEND: 'local', TASK_BACKEND: 'local', LOCAL_AUTH_BYPASS: 'true', NEXT_PUBLIC_APP_ENV: 'local', NEXT_PUBLIC_LOCAL_AUTH_BYPASS: 'true', ...process.env }
if (env.ENVIRONMENT !== 'local') throw new Error('npm run dev requires ENVIRONMENT=local')
const python = path.join(root, 'backend/.venv/bin/python')
if (!existsSync(python)) {
  execFileSync('python3', ['-m', 'venv', 'backend/.venv'], { stdio: 'inherit' })
  execFileSync(python, ['-m', 'pip', 'install', '-r', 'backend/requirements-dev.txt'], { stdio: 'inherit' })
}
execFileSync('docker', ['compose', 'up', '-d', '--wait'], { stdio: 'inherit' })
execFileSync(python, ['scripts/create_local_signer.py'], { stdio: 'inherit' })
env.ESIGN_LOCAL_SIGNING_KEY_PATH = path.join(root, '.local/signing-key.pem')
env.ESIGN_SIGNING_CERT_PATH = path.join(root, '.local/signing-cert.pem')
execFileSync(python, ['-m', 'alembic', 'upgrade', 'head'], { cwd: path.join(root, 'backend'), env, stdio: 'inherit' })
const processes = []
let stopping = false
function stop(code = 0) { if (stopping) return; stopping = true; clearInterval(maintenance); for (const child of processes) child.kill('SIGTERM'); process.exitCode = code }
function start(command, args, cwd) { const child = spawn(command, args, { cwd, env, stdio: 'inherit' }); child.on('exit', code => { if (!stopping) stop(code || 1) }); processes.push(child) }
start(python, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8100'], path.join(root, 'backend'))
start(python, ['-m', 'uvicorn', 'worker:app', '--host', '127.0.0.1', '--port', '8101'], path.join(root, 'backend'))
start(path.join(root, 'node_modules/.bin/next'), ['dev', '--hostname', '127.0.0.1', '--port', '3100'], root)
let runningMaintenance = false
const maintenance = setInterval(async () => {
  if (runningMaintenance) return
  runningMaintenance = true
  try { const response = await fetch('http://127.0.0.1:8101/tasks/maintenance', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); if (!response.ok) console.error('Maintenance failed:', response.status) }
  catch (error) { console.error('Maintenance worker unavailable:', error.message) }
  finally { runningMaintenance = false }
}, 30000)
process.on('SIGINT', () => stop()); process.on('SIGTERM', () => stop())
console.log('esign: http://localhost:3100 — captured mail: http://localhost:8025')
