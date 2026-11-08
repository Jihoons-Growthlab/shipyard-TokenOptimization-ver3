// 단일 API 클라이언트. 토큰은 sessionStorage `swp_token`. 오류는 서버 본문 {code,message,details}를 그대로 전달한다.
export const TOKEN_KEY = 'swp_token'

export class ApiError extends Error {
  constructor(status, body = {}) {
    super(body.message || '요청을 처리할 수 없습니다.')
    this.status = status
    this.code = body.code || 'HTTP_ERROR'
    this.details = body.details || {}
  }
}

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

let unauthorizedHandler = () => {}
/** 토큰을 쓴 요청이 401이면 호출된다(세션 정리 후 /login 이동). */
export function onUnauthorized(fn) { unauthorizedHandler = fn }

function buildUrl(path, query) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query || {})) {
    if (v !== undefined && v !== null && v !== '') qs.append(k, v)
  }
  const s = qs.toString()
  return s ? `${path}?${s}` : path
}

/**
 * @param {string} method
 * @param {string} path  `/api/...`
 * @param {{query?:object, body?:any, raw?:Blob|ArrayBuffer, contentType?:string, as?:'json'|'blob', token?:string, auth?:boolean}} opts
 */
export async function request(method, path, opts = {}) {
  const headers = {}
  const token = opts.token ?? (opts.auth === false ? null : tokenStore.get())
  if (token) headers.Authorization = `Bearer ${token}`
  let body
  if (opts.raw !== undefined) {
    body = opts.raw
    headers['Content-Type'] = opts.contentType || 'application/octet-stream'
  } else if (opts.body !== undefined) {
    body = JSON.stringify(opts.body)
    headers['Content-Type'] = 'application/json'
  }
  let res
  try {
    res = await fetch(buildUrl(path, opts.query), { method, headers, body })
  } catch {
    throw new ApiError(0, { code: 'NETWORK_ERROR', message: '서버에 연결할 수 없습니다.' })
  }
  if (!res.ok) {
    let data = {}
    try { data = await res.json() } catch { /* 본문 없음 */ }
    const err = new ApiError(res.status, data)
    if (res.status === 401 && token && !opts.token) unauthorizedHandler(err)
    throw err
  }
  if (res.status === 204) return null
  if (opts.as === 'blob') return res.blob()
  const text = await res.text()
  return text ? JSON.parse(text) : null
}

export const api = {
  get: (path, query, opts) => request('GET', path, { ...opts, query }),
  post: (path, body, opts) => request('POST', path, { ...opts, body }),
  put: (path, body, opts) => request('PUT', path, { ...opts, body }),
  patch: (path, body, opts) => request('PATCH', path, { ...opts, body }),
  del: (path, opts) => request('DELETE', path, opts),
  upload: (path, file, query) => request('POST', path, { query, raw: file, contentType: file.type || 'application/pdf' }),
  blob: (path) => request('GET', path, { as: 'blob' }),
}
