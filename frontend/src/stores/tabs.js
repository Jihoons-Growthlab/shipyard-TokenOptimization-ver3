// 셸 탭 상태. 키 `${token}:${param??''}`, 최대 12개, sessionStorage `swp_tabs`에 {tabs:[{token,param}],active} 저장.
import { reactive } from 'vue'

export const TABS_KEY = 'swp_tabs'
export const MAX_TABS = 12
export const LIMIT_MSG = '탭은 최대 12개까지 열 수 있습니다. 사용하지 않는 탭을 닫아주세요.'
export const DENY_MSG = '해당 화면에 대한 권한이 없습니다.'
export const tabKey = (token, param) => `${token}:${param ?? ''}`

/**
 * @param {{allowed:(token:string)=>boolean, access:(token:string)=>Promise<any>, notify:(msg:string,kind?:string)=>void, storage?:Storage}} deps
 */
export function createTabs({ allowed, access, notify, storage = sessionStorage }) {
  const state = reactive({ tabs: [], active: null })

  function persist() {
    const active = state.tabs.findIndex((t) => t.key === state.active)
    try {
      storage.setItem(TABS_KEY, JSON.stringify({ tabs: state.tabs.map(({ token, param }) => ({ token, param })), active }))
    } catch { /* 저장 불가 */ }
  }

  function add(token, param) {
    const tab = { key: tabKey(token, param), token, param: param ?? null, ctx: 0 }
    state.tabs.push(tab)
    return tab
  }

  /** 화면 이동. 권한 없음·개수 초과면 false. 이미 열린 탭이면 param 맥락을 다시 적용한다. */
  function open(token, param = null) {
    if (!allowed(token)) { notify(DENY_MSG, 'error'); return false }
    const key = tabKey(token, param)
    const found = state.tabs.find((t) => t.key === key)
    if (found) {
      found.ctx++
      state.active = key
      persist()
      return true
    }
    if (state.tabs.length >= MAX_TABS) { notify(LIMIT_MSG, 'error'); return false }
    add(token, param)
    state.active = key
    persist()
    Promise.resolve()
      .then(() => access(token))
      .catch((e) => {
        if (e?.status === 403) { close(key); notify(e.message || DENY_MSG, 'error') }
      })
    return true
  }

  function close(key) {
    const i = state.tabs.findIndex((t) => t.key === key)
    if (i < 0) return
    state.tabs.splice(i, 1)
    if (state.active === key) state.active = (state.tabs[i] || state.tabs[i - 1])?.key ?? null
    persist()
  }

  function closeOthers() {
    state.tabs.splice(0, state.tabs.length, ...state.tabs.filter((t) => t.key === state.active))
    persist()
  }

  /** 저장된 탭 중 권한 있는 화면만 복구. 남는 게 없으면 fallback 화면을 연다. */
  function restore(fallback) {
    let saved = null
    try { saved = JSON.parse(storage.getItem(TABS_KEY) || 'null') } catch { saved = null }
    const list = Array.isArray(saved?.tabs) ? saved.tabs : []
    const activeSaved = list[saved?.active]
    for (const t of list) {
      if (t && allowed(t.token) && !state.tabs.some((x) => x.key === tabKey(t.token, t.param))) add(t.token, t.param)
    }
    if (!state.tabs.length) {
      if (fallback) open(fallback)
      return
    }
    const ak = activeSaved && tabKey(activeSaved.token, activeSaved.param)
    state.active = state.tabs.some((t) => t.key === ak) ? ak : state.tabs[0].key
    persist()
  }

  function reset() {
    state.tabs.splice(0)
    state.active = null
    try { storage.removeItem(TABS_KEY) } catch { /* 무시 */ }
  }

  return { state, open, close, closeOthers, restore, reset }
}
