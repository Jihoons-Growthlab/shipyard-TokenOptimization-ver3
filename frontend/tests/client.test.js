import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api, ApiError, onUnauthorized, tokenStore } from '../src/api/client.js'

function reply(status, body) {
  return Promise.resolve(new Response(body === undefined ? null : JSON.stringify(body), { status }))
}

describe('api client', () => {
  beforeEach(() => { sessionStorage.clear(); vi.restoreAllMocks() })

  it('sends bearer token and query', async () => {
    tokenStore.set('t1')
    const f = vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(200, { ok: 1 }))
    expect(await api.get('/api/hulls', { q: 'a', status: '' })).toEqual({ ok: 1 })
    expect(f.mock.calls[0][0]).toBe('/api/hulls?q=a')
    expect(f.mock.calls[0][1].headers.Authorization).toBe('Bearer t1')
  })

  it('maps error body and calls 401 handler only with token', async () => {
    const h = vi.fn()
    onUnauthorized(h)
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(401, { code: 'UNAUTHORIZED', message: '세션', details: {} }))
    await expect(api.get('/api/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(h).not.toHaveBeenCalled()
    tokenStore.set('t1')
    const err = await api.get('/api/auth/me').catch((e) => e)
    expect(err.code).toBe('UNAUTHORIZED')
    expect(err.message).toBe('세션')
    expect(h).toHaveBeenCalledOnce()
  })

  it('returns null for 204', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(204))
    expect(await api.del('/api/blocks/1')).toBeNull()
  })
})
