// `YYYY-MM-DD` 날짜 연산(UTC 기준, 시간대 영향 없음).
const DAY = 86400000
export const parseD = (s) => { const [y, m, d] = s.split('-').map(Number); return Date.UTC(y, m - 1, d) }
export const fmtD = (t) => new Date(t).toISOString().slice(0, 10)
export const addDays = (s, n) => fmtD(parseD(s) + n * DAY)
export const diffDays = (a, b) => Math.round((parseD(a) - parseD(b)) / DAY)
export const dash = (v) => (v === null || v === undefined || v === '' ? '-' : v)
/** 빈 문자열은 null, 그 외 숫자로 */
export const numOrNull = (v) => (v === '' || v === null || v === undefined ? null : Number(v))
export const blankNull = (v) => (v === '' || v === undefined ? null : v)
