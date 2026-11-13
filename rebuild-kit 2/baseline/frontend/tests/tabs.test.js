import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createTabs, DENY_MSG, LIMIT_MSG, TABS_KEY, tabKey } from '../src/stores/tabs.js'

const flush = () => new Promise((r) => setTimeout(r, 0))

function make(allowedTokens = ['dashboard', 'hull-list', 'plan-gantt', 'progress'], access = vi.fn(() => Promise.resolve())) {
  const notify = vi.fn()
  const tabs = createTabs({ allowed: (t) => allowedTokens.includes(t), access, notify })
  return { tabs, notify, access }
}

describe('shell tabs', () => {
  beforeEach(() => sessionStorage.clear())

  it('reuses same key and re-applies param context (SHELL-T02)', async () => {
    const { tabs, access } = make()
    tabs.open('plan-gantt', '8001')
    tabs.open('hull-list')
    tabs.open('plan-gantt', '8001')
    await flush()
    expect(tabs.state.tabs.map((t) => t.key)).toEqual(['plan-gantt:8001', 'hull-list:'])
    expect(tabs.state.active).toBe(tabKey('plan-gantt', '8001'))
    expect(tabs.state.tabs[0].ctx).toBe(1)
    expect(access).toHaveBeenCalledTimes(2)
  })

  it('rejects 13th tab and keeps existing (SHELL-T03)', () => {
    const { tabs, notify } = make()
    for (let i = 0; i < 12; i++) expect(tabs.open('plan-gantt', String(i))).toBe(true)
    expect(tabs.open('progress')).toBe(false)
    expect(notify).toHaveBeenCalledWith(LIMIT_MSG, 'error')
    expect(tabs.state.tabs).toHaveLength(12)
    expect(tabs.state.active).toBe('plan-gantt:11')
  })

  it('denies navigate without permission', () => {
    const { tabs, notify } = make(['dashboard'])
    expect(tabs.open('user-mgmt')).toBe(false)
    expect(notify).toHaveBeenCalledWith(DENY_MSG, 'error')
  })

  it('closes tab when menu-access returns 403', async () => {
    const access = vi.fn(() => Promise.reject(Object.assign(new Error('권한이 없습니다.'), { status: 403 })))
    const { tabs, notify } = make(undefined, access)
    tabs.open('hull-list')
    await flush()
    expect(tabs.state.tabs).toHaveLength(0)
    expect(notify).toHaveBeenCalledWith('권한이 없습니다.', 'error')
  })

  it('activates next tab at same position on close, closeOthers keeps active', () => {
    const { tabs } = make()
    tabs.open('dashboard'); tabs.open('hull-list'); tabs.open('progress')
    tabs.state.active = 'hull-list:'
    tabs.close('hull-list:')
    expect(tabs.state.active).toBe('progress:')
    tabs.close('progress:')
    expect(tabs.state.active).toBe('dashboard:')
    tabs.open('hull-list')
    tabs.closeOthers()
    expect(tabs.state.tabs.map((t) => t.key)).toEqual(['hull-list:'])
  })

  it('restores only permitted tabs, else falls back (SHELL-T05)', () => {
    sessionStorage.setItem(TABS_KEY, JSON.stringify({ tabs: [{ token: 'user-mgmt', param: null }, { token: 'hull-list', param: null }], active: 0 }))
    const { tabs, access } = make(['dashboard', 'hull-list'])
    tabs.restore('dashboard')
    expect(tabs.state.tabs.map((t) => t.key)).toEqual(['hull-list:'])
    expect(tabs.state.active).toBe('hull-list:')
    expect(access).not.toHaveBeenCalled()
    expect(JSON.parse(sessionStorage.getItem(TABS_KEY))).toEqual({ tabs: [{ token: 'hull-list', param: null }], active: 0 })

    sessionStorage.setItem(TABS_KEY, JSON.stringify({ tabs: [{ token: 'user-mgmt' }], active: 0 }))
    const other = make(['dashboard'])
    other.tabs.restore('dashboard')
    expect(other.tabs.state.tabs.map((t) => t.key)).toEqual(['dashboard:'])
  })
})
