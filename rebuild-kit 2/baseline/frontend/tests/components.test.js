import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../src/api/client.js', () => ({ api: { get: vi.fn() } }))
const { api } = await import('../src/api/client.js')
const { default: WeatherWidget } = await import('../src/components/WeatherWidget.vue')
const { default: AppModal } = await import('../src/components/AppModal.vue')

const sample = (region, tempC) => ({ region, source: 'SAMPLE', obsDt: 'x', tempC, condition: '맑음', humidity: 52, windMs: 3.2, error: 'no provider' })

describe('WeatherWidget', () => {
  beforeEach(() => { localStorage.clear(); api.get.mockReset() })

  it('requests default region and shows sample badge, never LIVE (WEATHER-T01/T02)', async () => {
    api.get.mockResolvedValue(sample('울산', 17.6))
    const w = mount(WeatherWidget)
    await flushPromises()
    expect(api.get).toHaveBeenCalledWith('/api/weather', { region: '울산' })
    expect(w.text()).toContain('17.6℃')
    expect(w.text()).toContain('샘플')
    expect(w.text()).not.toContain('LIVE')
    w.unmount()
  })

  it('ignores late response after region change (WEATHER-T03)', async () => {
    let resolveFirst
    api.get.mockImplementationOnce(() => new Promise((r) => { resolveFirst = r }))
    api.get.mockImplementationOnce(() => Promise.resolve(sample('거제', 18.9)))
    const w = mount(WeatherWidget)
    await w.find('select').setValue('거제')
    await flushPromises()
    resolveFirst(sample('울산', 17.6))
    await flushPromises()
    expect(w.text()).toContain('18.9℃')
    expect(localStorage.getItem('swp_region')).toBe('거제')
    w.unmount()
  })

  it('shows failure text', async () => {
    api.get.mockRejectedValue(new Error('x'))
    const w = mount(WeatherWidget)
    await flushPromises()
    expect(w.text()).toContain('날씨 조회 실패')
    w.unmount()
  })
})

describe('AppModal (SHELL-T04)', () => {
  it('emits close on Esc, button and backdrop', async () => {
    const m = mount(AppModal, { props: { title: 'T' }, attachTo: document.body })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    document.querySelector('.mclose').click()
    document.querySelector('.mbg').dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    expect(m.emitted('close')).toHaveLength(3)
    m.unmount()
  })
})
