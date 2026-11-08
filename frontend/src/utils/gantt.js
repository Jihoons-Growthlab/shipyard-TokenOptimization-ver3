// 간트 좌표 계산 (specs/F05.md). x는 타임라인 영역(왼쪽 열 제외) 기준 px.
import { addDays, diffDays } from './date.js'

export const LEFT = 230
export const ROW = 28
export const HEAD = 34
export const SCALES = [{ v: 2.5, l: '축소' }, { v: 4, l: '보통' }, { v: 6, l: '확대' }]

export function ganttLayout(plans, today, scale) {
  let min = addDays(today, -5)
  let max = addDays(today, 5)
  for (const p of plans) {
    if (p.plan_start_dt && p.plan_start_dt < min) min = p.plan_start_dt
    if (p.plan_end_dt && p.plan_end_dt > max) max = p.plan_end_dt
  }
  const start = `${min.slice(0, 8)}01`
  const days = diffDays(max, start) + 8
  const width = LEFT + Math.ceil(days * scale)
  const x = (d) => diffDays(d, start) * scale
  const months = []
  let [y, m] = start.split('-').map(Number)
  for (;;) {
    const mm = String(m).padStart(2, '0')
    const off = diffDays(`${y}-${mm}-01`, start)
    if (off >= days) break
    months.push({ label: `${y}.${mm}`, x: off * scale })
    if (++m > 12) { m = 1; y++ }
  }
  const bars = plans.map((p, i) => ({
    plan: p,
    top: i * ROW,
    left: x(p.plan_start_dt),
    width: (diffDays(p.plan_end_dt, p.plan_start_dt) + 1) * scale,
  }))
  return { start, days, width, timeline: width - LEFT, months, todayX: x(today), bars, x }
}

/** 선행 종료+1일 지점 → 4px 오른쪽 → 수직 → 후행 시작. 보이는 공정끼리만. */
export function depPaths(deps, plans, layout, scale) {
  const rows = new Map(plans.map((p, i) => [p.plan_id, { p, i }]))
  const out = []
  for (const d of deps) {
    const a = rows.get(d.pred_plan_id)
    const b = rows.get(d.plan_id)
    if (!a || !b) continue
    const x1 = layout.x(a.p.plan_end_dt) + scale
    const y1 = a.i * ROW + ROW / 2
    const y2 = b.i * ROW + ROW / 2
    out.push(`M${x1} ${y1}H${x1 + 4}V${y2}H${layout.x(b.p.plan_start_dt)}`)
  }
  return out
}
