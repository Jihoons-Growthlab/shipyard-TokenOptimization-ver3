// 목록 행 마우스오버 미리보기(명세 외 요청 기능). 잠깐 머물면 열고, 행·카드 밖으로 나가면 닫는다. 결과는 키별로 캐시한다.
import { onBeforeUnmount, reactive } from 'vue'

const OPEN_MS = 280
const CLOSE_MS = 160
const TTL_MS = 30_000 // 목록 탭은 계속 살아 있으므로 오래된 미리보기를 다시 불러온다.

export function useHoverPreview(loader, { onDispose, ttl = TTL_MS } = {}) {
  const pv = reactive({ key: null, data: null, error: '', pos: null })
  const cache = new Map()
  let openT = 0
  let closeT = 0

  function enter(key, ev) {
    clearTimeout(closeT)
    if (pv.key === key) return
    clearTimeout(openT)
    const r = ev.currentTarget.getBoundingClientRect()
    const pos = { x: ev.clientX, top: r.top, bottom: r.bottom }
    openT = setTimeout(() => show(key, pos), OPEN_MS)
  }

  async function show(key, pos) {
    const hit = cache.get(key)
    const fresh = hit && Date.now() - hit.at < ttl
    Object.assign(pv, { key, pos, error: '', data: fresh ? hit.data : null })
    if (fresh) return
    try {
      const d = await loader(key)
      if (hit && onDispose) onDispose(hit.data)
      cache.set(key, { data: d, at: Date.now() })
      if (pv.key === key) pv.data = d
    } catch (e) {
      if (pv.key === key) pv.error = e.message || '미리보기를 불러오지 못했습니다.'
    }
  }

  function leave() {
    clearTimeout(openT)
    closeT = setTimeout(close, CLOSE_MS)
  }
  function keep() { clearTimeout(closeT) }
  function close() {
    clearTimeout(openT)
    pv.key = null
  }
  function clear() {
    if (onDispose) for (const v of cache.values()) onDispose(v.data)
    cache.clear()
  }

  onBeforeUnmount(() => {
    clearTimeout(openT)
    clearTimeout(closeT)
    clear()
  })
  return { pv, enter, leave, keep, close, clear }
}
