// 로그인 사용자·메뉴·공통 코드·토스트. 셸과 모든 화면이 공유한다.
import { reactive } from 'vue'
import { api } from '../api/client.js'

export const session = reactive({ me: null, menu: [], codes: {} })

export async function loadSession() {
  const [me, menu, codes] = await Promise.all([api.get('/api/auth/me'), api.get('/api/me/menu'), api.get('/api/codes')])
  Object.assign(session, { me, menu, codes })
}

export function clearSession() {
  Object.assign(session, { me: null, menu: [], codes: {} })
}

export const menuByToken = (token) => session.menu.find((m) => m.token && m.token === token) || null
export const codeList = (group) => session.codes[group] || []
export const codeName = (group, code) => codeList(group).find((c) => c.code === code)?.name ?? code ?? ''
export const userLabel = (u) => `${u.display_name} (${u.emp_no})`

export const toasts = reactive([])
let toastSeq = 0
/** kind: '' | 'error' | 'success' */
export function toast(message, kind = '') {
  const id = ++toastSeq
  toasts.push({ id, message, kind })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, 3200)
}
export const fail = (e) => toast(e?.message || '요청을 처리할 수 없습니다.', 'error')
