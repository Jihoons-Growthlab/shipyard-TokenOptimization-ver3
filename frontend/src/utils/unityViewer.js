// Unity 샘플 3D 뷰어 수명주기(프론트 전용). 인스턴스는 동시에 하나다.
export const BUILD_BASE = '/unity/ship-viewer/Build/'
export const NOT_FOUND_MSG = '3D 뷰어 빌드를 찾을 수 없습니다.'
export const TIMEOUT_MSG = '3D 뷰어가 응답하지 않습니다.'
export const LOADER_MSG = '3D 뷰어 로더를 불러오지 못했습니다.'
export const READY_EVENT = 'shipviewer-ready'
export const VIEWS = ['front', 'side', 'top', 'reset']
const KEYS = ['loaderUrl', 'dataUrl', 'frameworkUrl', 'codeUrl']

export function firstLine(e) {
  const msg = typeof e === 'string' ? e : (e?.message ?? String(e ?? ''))
  return msg.split('\n')[0].trim() || '알 수 없는 오류'
}

export async function fetchConfig(fetchImpl = globalThis.fetch) {
  let res
  try { res = await fetchImpl(`${BUILD_BASE}build.json`, { cache: 'no-store' }) } catch { throw new Error(NOT_FOUND_MSG) }
  if (!res.ok) throw new Error(NOT_FOUND_MSG)
  let cfg
  try { cfg = JSON.parse(await res.text()) } catch { throw new Error(NOT_FOUND_MSG) } // SPA 폴백(index.html)
  if (!cfg || KEYS.some((k) => typeof cfg[k] !== 'string')) throw new Error(NOT_FOUND_MSG)
  return cfg
}

let loader = null // { src, promise }

// 첫 진입에 한 번만 불러온다. 실패하면 태그를 지워 재시도를 허용한다.
export function loadLoader(src, doc = document) {
  if (loader && loader.src === src) return loader.promise
  const promise = new Promise((resolve, reject) => {
    const el = doc.createElement('script')
    el.src = src
    el.async = true
    el.dataset.unityLoader = ''
    el.onload = () => resolve()
    el.onerror = () => {
      el.remove()
      if (loader?.promise === promise) loader = null
      reject(new Error(LOADER_MSG))
    }
    doc.head.appendChild(el)
  })
  loader = { src, promise }
  return promise
}

export function loseContext(canvas) {
  try {
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    gl?.getExtension('WEBGL_lose_context')?.loseContext()
  } catch { /* 무시 */ }
}

const quitted = new WeakSet()
async function quit(inst) {
  if (!inst || quitted.has(inst)) return
  quitted.add(inst)
  try { await inst.Quit() } catch { /* 종료 경고 무시 */ }
}

let chain = Promise.resolve()
const LATE = Symbol('late')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/**
 * canvas(id 필수)에 뷰어를 시작한다. cb: onProgress(0~1), onReady(), onError(message).
 * 반환: { stop(): Promise, setView(view), done: Promise }
 */
export function startViewer(canvas, cb = {}, opts = {}) {
  const env = {
    fetch: opts.fetch ?? ((...a) => globalThis.fetch(...a)),
    loadScript: opts.loadScript ?? ((src) => loadLoader(src)),
    create: opts.create ?? (() => globalThis.createUnityInstance),
    timeoutMs: opts.timeoutMs ?? 20000,
    settleMs: opts.settleMs ?? 30000,
    dpr: opts.dpr ?? Math.min(globalThis.devicePixelRatio || 1, 2),
  }
  const s = { closed: false, instance: null, signal: false, ready: false, timer: null }
  let release
  const closedP = new Promise((r) => { release = r })
  const close = () => { if (!s.closed) { s.closed = true; release() } }
  const report = (e) => { if (s.closed) return; const msg = firstLine(e); close(); cb.onError?.(msg) }
  const maybeReady = () => {
    if (s.closed || s.ready || !s.instance || !s.signal) return
    s.ready = true
    clearTimeout(s.timer)
    cb.onReady?.()
  }
  const onSignal = () => { s.signal = true; maybeReady() }

  const prev = chain
  const session = (async () => {
    await prev.catch(() => {})
    let pending = null
    let listening = false
    try {
      if (s.closed) return
      if (!canvas?.id) throw new Error('canvas id가 없습니다.')
      const cfg = await fetchConfig(env.fetch)
      if (s.closed) return
      await env.loadScript(BUILD_BASE + cfg.loaderUrl)
      if (s.closed) return
      const create = env.create()
      if (typeof create !== 'function') throw new Error(LOADER_MSG)
      canvas.addEventListener(READY_EVENT, onSignal)
      listening = true
      const config = {
        dataUrl: BUILD_BASE + cfg.dataUrl,
        frameworkUrl: BUILD_BASE + cfg.frameworkUrl,
        codeUrl: BUILD_BASE + cfg.codeUrl,
        companyName: cfg.companyName,
        productName: cfg.productName,
        productVersion: cfg.productVersion,
        devicePixelRatio: env.dpr,
        // 6000.5 로더: showBanner(msg, type). type=error면 실패.
        showBanner: (msg, type) => { if (type === 'error') report(msg) },
      }
      pending = Promise.resolve().then(() => create(canvas, config, (p) => { if (!s.closed) cb.onProgress?.(p) }))
      const got = await Promise.race([pending, closedP.then(() => LATE)])
      if (got === LATE) return
      pending = null
      s.instance = got
      if (s.closed) return
      cb.onProgress?.(1)
      s.timer = setTimeout(() => { if (!s.ready) report(new Error(TIMEOUT_MSG)) }, env.timeoutMs)
      maybeReady()
    } catch (e) {
      report(e)
    } finally {
      await closedP
      clearTimeout(s.timer)
      if (listening) canvas.removeEventListener(READY_EVENT, onSignal)
      // 로딩 중 닫힘: 늦게 온 인스턴스를 받아 바로 종료한다.
      if (pending) {
        const p = pending
        p.then((i) => quit(i), () => {})
        await Promise.race([p.catch(() => null), sleep(env.settleMs)])
      }
      await quit(s.instance)
      s.instance = null
      if (canvas) loseContext(canvas)
    }
  })()
  chain = session

  return {
    done: session,
    get ready() { return s.ready },
    stop() { close(); return session },
    setView(view) {
      if (!s.ready || s.closed || !VIEWS.includes(view)) return false
      s.instance.SendMessage('ShipViewer', 'SetView', view)
      return true
    },
  }
}

// 테스트 전용
export function __resetForTest() { loader = null; chain = Promise.resolve() }
