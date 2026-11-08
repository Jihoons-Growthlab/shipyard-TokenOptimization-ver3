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
    expect(d).toBe(`M${x1} 14H${x1 + 4}V42H${31 * 4}`)
  })
})
