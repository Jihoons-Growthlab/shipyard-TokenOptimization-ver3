import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../src/api/client.js', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn(), patch: vi.fn(), put: vi.fn() } }))
const { api } = await import('../src/api/client.js')
const V = await import('../src/utils/unityViewer.js')
const { default: ShipViewer3D } = await import('../src/components/ShipViewer3D.vue')
const { default: HullDetail } = await import('../src/screens/HullDetail.vue')

const CFG = { loaderUrl: 'v.loader.js', dataUrl: 'v.data', frameworkUrl: 'v.framework.js', codeUrl: 'v.wasm', companyName: 'SWP', productName: 'ShipyardViewer', productVersion: '1.0' }
const okFetch = (body = JSON.stringify(CFG), ok = true) => vi.fn(async () => ({ ok, text: async () => body }))
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const fakeInstance = () => ({ Quit: vi.fn(async () => {}), SendMessage: vi.fn() })
const mkCanvas = (id = 'c1') => { const c = document.createElement('canvas'); c.id = id; document.body.appendChild(c); return c }
const lose = vi.fn()

HTMLCanvasElement.prototype.getContext = function () { return { getExtension: (n) => (n === 'WEBGL_lose_context' ? { loseContext: lose } : null) } }

function opts(over = {}) {
  return { fetch: okFetch(), loadScript: vi.fn(async () => {}), create: () => over.createFn, timeoutMs: 50, settleMs: 50, dpr: 1, ...over }
}

beforeEach(() => {
  V.__resetForTest()
  lose.mockClear()
  for (const f of Object.values(api)) f.mockReset()
  document.head.querySelectorAll('script[data-unity-loader]').forEach((e) => e.remove())
})

describe('fetchConfig (VIEWER-T04)', () => {
  it('uses no-store and treats SPA fallback / 404 as missing build', async () => {
    const f = okFetch()
    expect(await V.fetchConfig(f)).toEqual(CFG)
    expect(f).toHaveBeenCalledWith('/unity/ship-viewer/Build/build.json', { cache: 'no-store' })
    await expect(V.fetchConfig(okFetch('<!doctype html><html></html>'))).rejects.toThrow(V.NOT_FOUND_MSG)
    await expect(V.fetchConfig(okFetch('', false))).rejects.toThrow(V.NOT_FOUND_MSG)
    await expect(V.fetchConfig(okFetch('{"a":1}'))).rejects.toThrow(V.NOT_FOUND_MSG)
  })
})

describe('loadLoader (VIEWER-T06)', () => {
  it('loads once, removes tag on failure and allows retry', async () => {
    const p1 = V.loadLoader('/x.loader.js')
    const tag = document.head.querySelector('script[data-unity-loader]')
    tag.onerror()
    await expect(p1).rejects.toThrow(V.LOADER_MSG)
    expect(document.head.querySelectorAll('script[data-unity-loader]')).toHaveLength(0)
    const p2 = V.loadLoader('/x.loader.js')
    expect(V.loadLoader('/x.loader.js')).toBe(p2)
    const tags = document.head.querySelectorAll('script[data-unity-loader]')
    expect(tags).toHaveLength(1)
    tags[0].onload()
    await expect(p2).resolves.toBeUndefined()
    expect(V.loadLoader('/x.loader.js')).toBe(p2)
  })
})

describe('startViewer', () => {
  it('is ready only with instance + signal, sends views, quits and releases context', async () => {
    const inst = fakeInstance()
    const create = vi.fn(async (canvas, config, onProgress) => { onProgress(0.5); return inst })
    const cb = { onReady: vi.fn(), onError: vi.fn(), onProgress: vi.fn() }
    const canvas = mkCanvas()
    const h = V.startViewer(canvas, cb, opts({ createFn: create }))
    await flushPromises()
    const config = create.mock.calls[0][1]
    expect(config.codeUrl).toBe('/unity/ship-viewer/Build/v.wasm')
    expect(config.devicePixelRatio).toBe(1)
    expect(cb.onProgress).toHaveBeenCalledWith(0.5)
    expect(cb.onReady).not.toHaveBeenCalled()
    expect(h.setView('front')).toBe(false)
    canvas.dispatchEvent(new CustomEvent('shipviewer-ready'))
    expect(cb.onReady).toHaveBeenCalledTimes(1)
    expect(h.setView('side')).toBe(true)
    expect(inst.SendMessage).toHaveBeenCalledWith('ShipViewer', 'SetView', 'side')
    await h.stop()
    expect(inst.Quit).toHaveBeenCalledTimes(1)
    expect(lose).toHaveBeenCalled()
    expect(cb.onError).not.toHaveBeenCalled()
  })

  it('reports timeout when ready signal never arrives', async () => {
    const inst = fakeInstance()
    const cb = { onError: vi.fn() }
    const h = V.startViewer(mkCanvas(), cb, opts({ createFn: async () => inst }))
    await h.done
    expect(cb.onError).toHaveBeenCalledWith(V.TIMEOUT_MSG)
    expect(inst.Quit).toHaveBeenCalled()
  })

  it('shows first line only for banner / load errors', async () => {
    const cb = { onError: vi.fn() }
    const create = async (c, config) => { config.showBanner('wasm 실패\n  at stack', 'error'); throw new Error('wasm 실패\nstack') }
    await V.startViewer(mkCanvas(), cb, opts({ createFn: create })).done
    expect(cb.onError).toHaveBeenCalledTimes(1)
    expect(cb.onError).toHaveBeenCalledWith('wasm 실패')
    const cb2 = { onError: vi.fn() }
    await V.startViewer(mkCanvas('c2'), cb2, opts({ fetch: okFetch('<html>') })).done
    expect(cb2.onError).toHaveBeenCalledWith(V.NOT_FOUND_MSG)
  })

  it('quits late instance when closed during loading and next start waits for it', async () => {
    const d = deferred()
    const late = fakeInstance()
    const order = []
    late.Quit = vi.fn(async () => { order.push('quit-old') })
    const cb = { onReady: vi.fn(), onError: vi.fn() }
    const h1 = V.startViewer(mkCanvas(), cb, opts({ createFn: () => d.promise, settleMs: 1000 }))
    await flushPromises()
    h1.stop()
    const create2 = vi.fn(async () => { order.push('create-new'); return fakeInstance() })
    const h2 = V.startViewer(mkCanvas('c2'), {}, opts({ createFn: create2 }))
    await flushPromises()
    expect(create2).not.toHaveBeenCalled()
    d.resolve(late)
    await h1.done
    await flushPromises()
    expect(late.Quit).toHaveBeenCalledTimes(1)
    expect(order).toEqual(['quit-old', 'create-new'])
    expect(cb.onReady).not.toHaveBeenCalled()
    expect(cb.onError).not.toHaveBeenCalled()
    await h2.stop()
  })
})

describe('ShipViewer3D (VIEWER-T02/T04/T05)', () => {
  it('opens the hull mapped to a Unity berth slot', async () => {
    const inst = fakeInstance()
    const w = mount(ShipViewer3D, {
      props: {
        fleet: [{ hull_no: '8001' }, { hull_no: '8002', hull_status: 'BUILD', progress: 65, delay_count: 2, delivery_dt: '2026-12-01' }],
        options: opts({ createFn: async () => inst }),
      },
    })
    try {
      await flushPromises()
      const canvas = w.find('canvas').element
      canvas.dispatchEvent(new CustomEvent(V.READY_EVENT))
      expect(inst.SendMessage).toHaveBeenCalledWith('ShipViewer', 'SetFleet', '2')
      await w.find('canvas').trigger('pointerenter')
      canvas.dispatchEvent(new CustomEvent('shipyard-hover', { detail: 1 }))
      await flushPromises()
      const summary = w.get('.twin-hover').text()
      for (const value of ['8002', 'BUILD', '65%', '2건', '2026-12-01']) {
        expect(summary).toContain(value)
      }
      canvas.dispatchEvent(new CustomEvent('shipyard-select', { detail: 1 }))
      expect(w.emitted('select')).toEqual([['8002']])
    } finally {
      w.unmount()
    }
  })

  it('shows API data only while hovering the ship in the ready canvas', async () => {
    api.get.mockResolvedValue({ hull_no: '8001', hull_nm: '테스트 호선', progress: 42, delay_count: 0 })
    const w = mount(ShipViewer3D, {
      props: { hullNo: '8001', options: opts({ createFn: async () => fakeInstance() }) },
    })
    try {
      await flushPromises()
      const canvas = w.find('canvas')
      canvas.element.dispatchEvent(new CustomEvent(V.READY_EVENT))
      await canvas.trigger('pointerenter')
      expect(w.find('.twin-hover').exists()).toBe(false)
      canvas.element.dispatchEvent(new CustomEvent('shipviewer-hover', { detail: true }))
      await flushPromises()
      expect(w.get('.twin-hover').text()).toContain('42%')
      await canvas.trigger('pointerleave')
      expect(w.find('.twin-hover').exists()).toBe(false)
      expect(api.get).toHaveBeenCalledWith('/api/hulls/8001')
    } finally {
      w.unmount()
    }
  })

  it('disables views before ready, retries with a new canvas', async () => {
    let fail = true
    const inst = fakeInstance()
    const create = vi.fn(async () => { if (fail) throw new Error('wasm 오류\nstack'); return inst })
    const w = mount(ShipViewer3D, { props: { options: opts({ createFn: create }) }, attachTo: document.body })
    expect(w.text()).toContain('3D 뷰어 불러오는 중…')
    expect(w.text()).toContain('호선 디지털 트윈')
    expect(w.text()).toContain('가상 조선소 · 예시 선체 형상')
    expect(w.text()).toContain('오른쪽 드래그')
    await flushPromises()
    await new Promise((r) => setTimeout(r, 0))
    await flushPromises()
    expect(w.text()).toContain('3D 뷰어를 불러오지 못했습니다.')
    expect(w.text()).toContain('wasm 오류')
    expect(w.text()).not.toContain('stack')
    const viewBtns = w.findAll('.views button')
    expect(viewBtns.map((b) => b.text())).toEqual(['정면', '측면', '상단', '초기화'])
    expect(viewBtns.every((b) => b.element.disabled)).toBe(true)
    const firstId = w.find('canvas').attributes('id')
    fail = false
    await w.find('.ovl button').trigger('click')
    await flushPromises()
    await new Promise((r) => setTimeout(r, 0))
    await flushPromises()
    const canvas = w.find('canvas')
    expect(canvas.attributes('id')).not.toBe(firstId)
    canvas.element.dispatchEvent(new CustomEvent('shipviewer-ready'))
    await flushPromises()
    expect(w.findAll('.views button').every((b) => !b.element.disabled)).toBe(true)
    await w.findAll('.views button')[3].trigger('click')
    expect(inst.SendMessage).toHaveBeenCalledWith('ShipViewer', 'SetView', 'reset')
    w.unmount()
    await flushPromises()
    expect(inst.Quit).toHaveBeenCalled()
  })

  it('does not accumulate canvases or listeners over 8 enter/leave cycles', async () => {
    const add = vi.spyOn(HTMLCanvasElement.prototype, 'addEventListener')
    const rem = vi.spyOn(HTMLCanvasElement.prototype, 'removeEventListener')
    const insts = []
    for (let i = 0; i < 8; i++) {
      const create = async () => { await new Promise((r) => setTimeout(r, i % 2 ? 0 : 5)); const x = fakeInstance(); insts.push(x); return x }
      const w = mount(ShipViewer3D, { props: { options: opts({ createFn: create }) }, attachTo: document.body })
      if (i % 2) await flushPromises() // 짝수 회차는 로딩 중 즉시 이탈
      w.unmount()
      expect(document.querySelectorAll('canvas[id^=ship-viewer-canvas]')).toHaveLength(0)
    }
    await new Promise((r) => setTimeout(r, 120))
    await flushPromises()
    const n = (s) => s.mock.calls.filter((c) => c[0] === 'shipviewer-ready').length
    expect(n(add)).toBe(n(rem))
    expect(insts.every((x) => x.Quit.mock.calls.length === 1)).toBe(true)
    add.mockRestore(); rem.mockRestore()
  })
})

describe('HullDetail 3D tab (VIEWER-T01)', () => {
  it('keeps unsaved info edits across a 3D tab round trip', async () => {
    api.get.mockImplementation(async (p) => (p === '/api/hulls/8001' ? { hull_no: '8001', hull_nm: '원본', hull_status: 'BUILD', use_yn: true } : []))
    globalThis.fetch = okFetch('<html>')
    const w = mount(HullDetail, { props: { hullNo: '8001', canWrite: true }, global: { provide: { navigate: vi.fn() } }, attachTo: document.body })
    await flushPromises()
    const tabs = () => [...document.querySelectorAll('.subtabs button')]
    expect(tabs().map((b) => b.textContent)).toContain('3D 보기')
    const input = document.querySelector('input[name=hull_nm]')
    input.value = '수정중'
    input.dispatchEvent(new Event('input'))
    tabs().find((b) => b.textContent === '3D 보기').click()
    await flushPromises()
    expect(document.querySelector('.modal').classList.contains('xl')).toBe(true)
    expect(document.body.textContent).toContain('8001 · 원본')
    tabs().find((b) => b.textContent === '기본정보').click()
    await flushPromises()
    expect(document.querySelector('input[name=hull_nm]').value).toBe('수정중')
    expect(api.get.mock.calls.filter((c) => c[0] === '/api/hulls/8001')).toHaveLength(2)
    w.unmount()
  })

  it('has no 3D tab for a new hull', async () => {
    const w = mount(HullDetail, { props: { hullNo: null, canWrite: true }, global: { provide: { navigate: vi.fn() } }, attachTo: document.body })
    await flushPromises()
    expect(document.body.textContent).not.toContain('3D 보기')
    w.unmount()
  })
})
