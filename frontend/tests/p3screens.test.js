import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../src/api/client.js', () => ({ api: { get: vi.fn(), post: vi.fn(), del: vi.fn(), patch: vi.fn() } }))
const { api } = await import('../src/api/client.js')
const { session, toasts } = await import('../src/stores/session.js')
const { default: ApprovalScreen } = await import('../src/screens/ApprovalScreen.vue')
const { default: UserMgmtScreen } = await import('../src/screens/UserMgmtScreen.vue')
const { default: DashboardScreen } = await import('../src/screens/DashboardScreen.vue')

const route = (map) => (p) => Promise.resolve(map[p])
const lastToast = () => toasts[toasts.length - 1]?.message

beforeEach(() => {
  for (const f of Object.values(api)) f.mockReset()
  toasts.splice(0)
  session.me = { emp_no: 'admin', display_name: '김관리', today: '2026-10-19' }
})

describe('ApprovalScreen (APV-T03/T06)', () => {
  const inbox = { waiting: [{ approval_id: 5, drawing_id: 1, drawing_no: 'D-1', drawing_nm: 'n', rev_no: 0, step_no: 2, change_desc: 'c' }], ready: [], can_issue: true }

  it('requires comment to reject, then posts and reloads', async () => {
    api.get.mockImplementation(route({ '/api/approvals/inbox': inbox, '/api/approvals/history': [] }))
    api.post.mockResolvedValue({})
    const w = mount(ApprovalScreen, { props: { canWrite: true } })
    await flushPromises()
    expect(w.text()).toContain('김관리 님의 결재 대기와 배포 대기 도면입니다.')
    expect(w.text()).toContain('배포 대기 도면이 없습니다.')
    expect(w.text()).toContain('결재 이력이 없습니다.')
    const reject = w.findAll('button').find((b) => b.text() === '반려')
    await reject.trigger('click')
    expect(api.post).not.toHaveBeenCalled()
    expect(lastToast()).toBe('반려 시 의견을 입력하세요.')
    await w.find('input[name=comment]').setValue('수정 필요')
    await reject.trigger('click')
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/api/approvals/5/decision', { result: 'REJECT', comment: '수정 필요' })
    expect(lastToast()).toBe('반려했습니다. 도면은 작성중으로 되돌려집니다.')
    expect(api.get.mock.calls.filter((c) => c[0] === '/api/approvals/inbox')).toHaveLength(2)
  })

  it('renders no decision buttons for view-only', async () => {
    api.get.mockImplementation(route({ '/api/approvals/inbox': inbox, '/api/approvals/history': [] }))
    const w = mount(ApprovalScreen, { props: { canWrite: false } })
    await flushPromises()
    expect(w.findAll('button').map((b) => b.text())).not.toContain('승인')
  })
})

describe('UserMgmtScreen (USR-T01/T06)', () => {
  const u = (emp_no, status = 'approved') => ({ emp_no, last_name: '김', first_name: '관리', display_name: emp_no, email: `${emp_no}@x`, phone: '010', birth_date: '1980-01-01', status, totp_enabled: false, groups: [{ code: 'ADMIN', name: '시스템관리자' }], created_at: '2026-01-05 00:00:00' })

  it('blocks self delete on client and shows approve for pending', async () => {
    api.get.mockImplementation(route({ '/api/users': { users: [u('admin'), u('jung.new', 'pending')], total: 2, pending: 1 }, '/api/auth-groups': [{ code: 'ADMIN', name: '시스템관리자' }] }))
    const w = mount(UserMgmtScreen, { props: { canWrite: true } })
    await flushPromises()
    expect(w.text()).toContain('2명 · 승인대기 1명')
    expect(w.text()).toContain('시스템관리자')
    expect(w.text()).toContain('목록에서 회원을 선택하거나 [신규]를 누르세요.')
    await w.findAll('tbody tr')[0].trigger('click')
    expect(w.text()).toContain('회원 수정 — admin')
    expect(w.find('input[name=emp_no]').attributes('readonly')).toBeDefined()
    await w.findAll('button').find((b) => b.text() === '삭제').trigger('click')
    expect(api.del).not.toHaveBeenCalled()
    expect(lastToast()).toBe('로그인 중인 본인 계정은 삭제할 수 없습니다.')
    expect(w.text()).not.toContain('가입 승인')
    await w.findAll('tbody tr')[1].trigger('click')
    expect(w.text()).toContain('가입 승인')
  })

  it('omits empty password on update (USR-T03)', async () => {
    api.get.mockImplementation(route({ '/api/users': { users: [u('park.pm')], total: 1, pending: 0 }, '/api/auth-groups': [] }))
    api.patch.mockResolvedValue(u('park.pm'))
    const w = mount(UserMgmtScreen, { props: { canWrite: true } })
    await flushPromises()
    await w.find('tbody tr').trigger('click')
    await w.find('form:not(.toolbar)').trigger('submit')
    await flushPromises()
    const body = api.patch.mock.calls[0][1]
    expect(api.patch.mock.calls[0][0]).toBe('/api/users/park.pm')
    expect(body).not.toHaveProperty('password')
    expect(body.groups).toEqual(['ADMIN'])
  })
})

describe('DashboardScreen (DASH-T05/T06)', () => {
  const item = (i) => ({ plan_id: i, hull_no: '8001', label: `[10${i}] 도장`, plan_status: 'DELAY', progress_rate: 60, plan_start_dt: '2026-10-01', plan_end_dt: '2026-10-10', blockers: ['D-1'], link: { screen: 'plan-gantt', param: '8001' } })
  const summary = {
    today: '2026-10-19',
    kpi: { active_hulls: { value: 4, link: { screen: 'hull-list' } }, delay_plans: { value: 7, link: { screen: 'plan-gantt' } }, waiting_plans: { value: 0, link: { screen: 'plan-gantt' } }, pending_drawings: { value: 6, link: { screen: 'dwg-approval' } } },
    hull_progress: [{ hull_no: '8001', hull_nm: 'A', progress: 65.4, link: { screen: 'plan-gantt', param: '8001' } }],
    plan_status: [{ status: 'PLAN', count: 3 }, { status: 'DONE', count: 1 }],
    drawing_disciplines: [{ discipline: 'HULL', name: '선체', total: 2, counts: { ISSUED: 2, APPROVED: 0, REVIEW: 0, DRAFT: 0 } }],
    deliveries: [{ month: '2026-12', count: 1, hull_nos: ['8005'] }],
    delay_list: { count: 7, items: [1, 2, 3, 4, 5, 6].map(item) },
    waiting_list: { count: 0, items: [] },
    impact_list: { count: 0, items: [] },
  }

  it('renders summary, caps lists, navigates by link', async () => {
    api.get.mockResolvedValue(summary)
    const navigate = vi.fn()
    const w = mount(DashboardScreen, { global: { provide: { navigate } } })
    await flushPromises()
    expect(w.text()).toContain('기준일 2026-10-19 · 호선/공정/도면 현황')
    expect(w.findAll('.li')).toHaveLength(6)
    expect(w.find('.b-bad').text()).toBe('7')
    expect(w.text()).toContain('대기 중인 공정이 없습니다.')
    expect(w.text()).toContain('최근 개정된 도면의 영향 공정이 없습니다.')
    expect(w.text()).toContain('65%')
    expect(w.findAll('.kpi b')[1].classes()).toContain('err')
    await w.findAll('.kpi')[3].trigger('click')
    expect(navigate).toHaveBeenLastCalledWith('dwg-approval', null)
    await w.find('.hp').trigger('click')
    expect(navigate).toHaveBeenLastCalledWith('plan-gantt', '8001')
  })
})
