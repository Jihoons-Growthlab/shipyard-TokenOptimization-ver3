import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../src/api/client.js', () => ({ api: { get: vi.fn(), blob: vi.fn(), upload: vi.fn(), post: vi.fn(), del: vi.fn(), patch: vi.fn() } }))
const { api } = await import('../src/api/client.js')
const { checkPdf, revText, fileLine, PDF_MAX, PDF_TYPE_MSG, PDF_SIZE_MSG } = await import('../src/utils/drawing.js')
const { default: DrawingDetail } = await import('../src/screens/DrawingDetail.vue')

const pdf = (body = '%PDF-1.4 x', name = 'a.pdf', type = 'application/pdf') => new File([body], name, { type })

describe('checkPdf (DWG-T04)', () => {
  it('accepts a real pdf', async () => { expect(await checkPdf(pdf())).toBeNull() })
  it('rejects non-pdf name and type', async () => { expect(await checkPdf(pdf('%PDF-', 'a.png', 'image/png'))).toBe(PDF_TYPE_MSG) })
  it('rejects wrong magic bytes', async () => { expect(await checkPdf(pdf('hello'))).toBe(PDF_TYPE_MSG) })
  it('rejects over 30MiB', async () => {
    const f = pdf()
    Object.defineProperty(f, 'size', { value: PDF_MAX + 1 })
    expect(await checkPdf(f)).toBe(PDF_SIZE_MSG)
  })
})

describe('labels (DWG-T01/T05)', () => {
  it('shows current and latest rev', () => {
    expect(revText({ current_rev_no: 0, latest_rev_no: 1 })).toEqual({ cur: 'Rev0', latest: ' (최신 Rev1)' })
    expect(revText({ current_rev_no: 2, latest_rev_no: 2 })).toEqual({ cur: 'Rev2', latest: '' })
  })
  it('marks seed files as not uploaded', () => {
    expect(fileLine({ file_nm: 'x.dwg', has_file: false })).toBe('x.dwg (미업로드)')
    expect(fileLine({ file_nm: null, has_file: false })).toBe('파일 없음')
  })
})

const detail = (status, hasFile = false) => ({
  drawing_id: 7, drawing_no: 'D-1', drawing_nm: '도면', hull_no: '8001', block_id: null, block_cd: null, block_nm: null,
  discipline: 'HULL', dwg_status: status, designer_emp_no: null,
  revisions: [{ rev_no: 1, rev_status: status, change_desc: 'c', has_file: hasFile, file_nm: hasFile ? 'a.pdf' : 'x.dwg', author_nm: 'a', issue_dt: null }],
  approvals: [], plans: [], available_plans: [], impacts: [],
})

function mountDetail(d, canWrite) {
  api.get.mockImplementation((p) => Promise.resolve(p.startsWith('/api/drawings/') ? d : []))
  return mount(DrawingDetail, { props: { drawingId: 7, canWrite }, global: { stubs: { teleport: true } } })
}

describe('DrawingDetail', () => {
  beforeEach(() => { api.get.mockReset(); api.blob.mockReset() })

  it('shows sample box without file and renders no write UI for view-only (DWG-T05/T10)', async () => {
    const w = mountDetail(detail('DRAFT'), false)
    await flushPromises()
    expect(w.text()).toContain('이 리비전에는 업로드된 도면 파일이 없습니다.')
    expect(w.text()).toContain('x.dwg (미업로드)')
    expect(w.find('input[type=file]').exists()).toBe(false)
    expect(w.text()).not.toContain('결재 요청')
    expect(w.findAll('button').map((b) => b.text())).toEqual(['닫기 ✕', '새 창으로 열기'])
    expect(api.blob).not.toHaveBeenCalled()
  })

  it('enables upload only for DRAFT (DWG-T04)', async () => {
    let w = mountDetail(detail('DRAFT'), true)
    await flushPromises()
    expect(w.find('input.vfile').attributes('disabled')).toBeUndefined()
    expect(w.text()).toContain('결재 요청')
    w = mountDetail(detail('ISSUED'), true)
    await flushPromises()
    expect(w.find('input.vfile').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('신규 Rev2 개정 사유')
  })

  it('loads uploaded pdf as blob url', async () => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()
    api.blob.mockResolvedValue(new Blob(['%PDF-']))
    const w = mountDetail(detail('DRAFT', true), true)
    await flushPromises()
    expect(api.blob).toHaveBeenCalledWith('/api/drawings/7/revisions/1/pdf')
    expect(w.find('iframe').attributes('src')).toBe('blob:x#view=FitH')
    w.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x')
  })
})
