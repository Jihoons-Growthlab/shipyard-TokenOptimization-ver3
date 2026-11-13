import { describe, it, expect } from 'vitest'
import { depPaths, ganttLayout, LEFT } from '../src/utils/gantt.js'

const plans = [
  { plan_id: 1, plan_start_dt: '2026-08-20', plan_end_dt: '2026-08-29' },
  { plan_id: 2, plan_start_dt: '2026-09-01', plan_end_dt: '2026-11-30' },
]

describe('gantt layout', () => {
  it('computes range, width, months and bars', () => {
    const L = ganttLayout(plans, '2026-10-19', 4)
    expect(L.start).toBe('2026-08-01')
    // end = 2026-11-30, days = 121 + 8
    expect(L.days).toBe(129)
    expect(L.width).toBe(LEFT + Math.ceil(129 * 4))
    expect(L.months.map((m) => m.label)).toEqual(['2026.08', '2026.09', '2026.10', '2026.11', '2026.12'])
    expect(L.bars[0]).toMatchObject({ left: 19 * 4, width: 10 * 4, top: 0 })
    expect(L.todayX).toBe(79 * 4)
  })

  it('uses today ±5 when plans are inside', () => {
    const L = ganttLayout([], '2026-10-03', 2.5)
    expect(L.start).toBe('2026-09-01')
    expect(L.days).toBe(37 + 8)
    expect(L.width).toBe(LEFT + Math.ceil(45 * 2.5))
  })

  it('draws dependency from pred end+1 to succ start', () => {
    const L = ganttLayout(plans, '2026-10-19', 4)
    const [d] = depPaths([{ plan_id: 2, pred_plan_id: 1 }, { plan_id: 2, pred_plan_id: 99 }], plans, L, 4)
    const x1 = 28 * 4 + 4
    expect(d).toEqual({ d: `M${x1} 14H${x1 + 4}V42H${31 * 4}`, from: 1, to: 2 })
  })
})

describe('offDays (주말·공휴일)', () => {
  it('marks weekends and Korean holidays, holiday wins over weekend', async () => {
    const { offDays } = await import('../src/utils/gantt.js')
    const L = ganttLayout([{ plan_id: 1, plan_start_dt: '2026-10-01', plan_end_dt: '2026-10-12' }], '2026-10-01', 4)
    const by = Object.fromEntries(offDays(L, 4).map((o) => [o.date, o]))
    expect(by['2026-10-03']).toMatchObject({ kind: 'hol', name: '개천절' }) // 토요일이지만 공휴일
    expect(by['2026-10-05'].kind).toBe('hol') // 대체공휴일(월)
    expect(by['2026-10-04'].kind).toBe('sun')
    expect(by['2026-10-10'].kind).toBe('sat')
    expect(by['2026-10-09'].name).toBe('한글날')
    expect(by['2026-10-06']).toBeUndefined()
    expect(by['2026-10-03'].x).toBe(L.x('2026-10-03'))
  })
})
