/** Host half of the THS simulated-account dashboard.
 *
 * Starts the local Python data service (ths_sim.dashboard_server) and exposes
 * a same-origin proxy at /ths-dashboard/api so the browser panel does not need
 * CORS, a fixed port, or any access to the THS cookie.
 */
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'dsh-ths-dashboard'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(HERE, '..')
const PYTHON_DIR = path.join(PACKAGE_ROOT, 'python')
const PORT = Number(process.env.THS_DASHBOARD_PORT || 8766)
const BASE = `http://127.0.0.1:${PORT}`
const LOG_PATH = path.join(os.tmpdir(), 'ths-dashboard-server.log')

function resolvePython() {
  const explicit = process.env.THS_DASHBOARD_PYTHON || process.env.DSH_PYTHON
  if (explicit) return explicit
  const candidates = [
    process.resourcesPath
      ? path.join(process.resourcesPath, 'runtime', 'primary-runtime', 'dependencies', 'python', 'python.exe')
      : '',
    path.join(os.homedir(), '.dsh', 'dsh-runtimes', 'dsh-primary-runtime', 'dependencies', 'python', 'python.exe'),
  ].filter(Boolean)
  for (const candidate of candidates) {
    try { if (fs.existsSync(candidate)) return candidate } catch (err) {}
  }
  return process.platform === 'win32' ? 'python' : 'python3'
}
const PYTHON = resolvePython()

let child = null
let starting = null
let stopped = false

function log(line) {
  try {
    fs.appendFileSync(LOG_PATH, `[${new Date().toISOString()}] ${line}\n`, 'utf8')
  } catch (err) {}
}

async function ping(timeoutMs = 1200) {
  try {
    const response = await fetch(`${BASE}/api/health`, {
      signal: AbortSignal.timeout(timeoutMs),
    })
    return response.ok
  } catch (err) {
    return false
  }
}

async function ensureServer() {
  if (stopped) return false
  if (await ping()) return true
  if (starting) return starting
  starting = (async () => {
    try {
      const logFd = fs.openSync(LOG_PATH, 'a')
      child = spawn(PYTHON, ['-m', 'ths_sim.dashboard_server', '--port', String(PORT)], {
        cwd: PACKAGE_ROOT,
        env: {
          ...process.env,
          PYTHONPATH: [PYTHON_DIR, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
          PYTHONIOENCODING: 'utf-8',
          PYTHONUNBUFFERED: '1',
        },
        windowsHide: true,
        stdio: ['ignore', logFd, logFd],
      })
      fs.closeSync(logFd)
      child.on('exit', (code, signal) => {
        log(`server exited code=${code} signal=${signal}`)
        child = null
      })
      child.on('error', (err) => {
        log(`server spawn error: ${err && err.message ? err.message : err}`)
        child = null
      })
      for (let i = 0; i < 30; i += 1) {
        await new Promise(resolve => setTimeout(resolve, 250))
        if (await ping(700)) return true
      }
      log('server did not become healthy in time')
      return false
    } catch (err) {
      log(`ensureServer failed: ${err && err.message ? err.message : err}`)
      return false
    } finally {
      starting = null
    }
  })()
  return starting
}

function stopServer() {
  stopped = true
  if (child) {
    try { child.kill() } catch (err) {}
    child = null
  }
}

async function proxy(req, res) {
  const incoming = new URL(req.url || '/ths-dashboard/api', 'http://127.0.0.1')
  const action = incoming.searchParams.get('action') || 'overview'
  const allowed = new Set(['overview', 'health', 'account', 'quote', 'kline', 'daily', 'flow', 'backtests', 'backtest', 'history', 'backtest_flow'])
  if (!allowed.has(action)) {
    res.writeHead(400, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify({ ok: false, error: 'unknown dashboard action' }))
    return
  }
  const target = new URL(`/api/${action}`, BASE)
  for (const [key, value] of incoming.searchParams.entries()) {
    if (key !== 'action') target.searchParams.set(key, value)
  }
  if (!(await ensureServer())) {
    res.writeHead(503, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify({
      ok: false,
      error: '本地行情服务未启动',
      hint: '请检查 %TEMP%\\ths-dashboard-server.log，或手动运行 python -m ths_sim.dashboard_server',
    }))
    return
  }
  try {
    const response = await fetch(target, { signal: AbortSignal.timeout(45_000) })
    const body = Buffer.from(await response.arrayBuffer())
    res.writeHead(response.status, {
      'Content-Type': response.headers.get('content-type') || 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'Content-Length': String(body.length),
    })
    res.end(body)
  } catch (err) {
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify({
      ok: false,
      error: '行情服务请求失败: ' + String(err && err.message ? err.message : err),
    }))
  }
}

export function apply(ctx) {
  ctx.inject(['webServer'], (host) => {
    ensureServer().catch(() => {})
    host.effect(() => () => stopServer(), 'dsh-ths-dashboard: python server')
    host.effect(() => host.webServer.register({
      kind: 'exact',
      path: '/ths-dashboard/api',
      handler: proxy,
    }), 'dsh-ths-dashboard: api proxy')
  })
}

export { ensureServer as _ensureServer }