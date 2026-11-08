// 도면·결재 화면 공통: PDF 검사/업로드, 참조 목록 조회, 표기 규칙.
import { api } from '../api/client.js'

export const PDF_MAX = 30 * 1024 * 1024
export const PDF_TYPE_MSG = 'PDF 파일만 업로드할 수 있습니다.'
export const PDF_SIZE_MSG = '파일 크기는 30MB 이하여야 합니다.'

function headText(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(String(r.result))
    r.onerror = () => reject(r.error)
    r.readAsText(file.slice(0, 5))
  })
}

/** 서버와 같은 기준(확장자/MIME, 30MiB, `%PDF-` 시작)으로 검사한다. 통과하면 null. */
export async function checkPdf(file) {
  if (!(/\.pdf$/i.test(file?.name || '') || file?.type === 'application/pdf')) return PDF_TYPE_MSG
  if (file.size > PDF_MAX) return PDF_SIZE_MSG
  if ((await headText(file)) !== '%PDF-') return PDF_TYPE_MSG
  return null
}

export const uploadPdf = (drawingId, revNo, file) =>
  api.upload(`/api/drawings/${drawingId}/revisions/${revNo}/pdf`, file, { filename: file.name })

/** 호선 선택 목록. 호선 메뉴 권한이 없으면 공정 호선 목록으로 대체한다. */
export async function loadHullOptions() {
  try { return await api.get('/api/hulls') } catch { return api.get('/api/plan-hulls') }
}
export async function loadBlocks(hullNo) {
  if (!hullNo) return []
  try { return await api.get(`/api/hulls/${hullNo}/blocks`) } catch { return [] }
}

export const STEP_NM = { 1: '검토', 2: '승인' }
export const RESULT_BADGE = { WAIT: ['대기', 'b-warn'], APPROVE: ['승인', 'b-ok'], REJECT: ['반려', 'b-bad'] }

/** 목록 Rev 표기: 현재(배포) Rev와, 다르면 최신 Rev. */
export function revText(d) {
  return {
    cur: d.current_rev_no === null || d.current_rev_no === undefined ? '-' : `Rev${d.current_rev_no}`,
    latest: d.latest_rev_no !== null && d.latest_rev_no !== undefined && d.latest_rev_no !== d.current_rev_no ? ` (최신 Rev${d.latest_rev_no})` : '',
  }
}

/** 리비전 파일 표기: 파일명(미업로드 표시) 또는 `파일 없음`. */
export const fileLine = (r) => (r.file_nm ? r.file_nm + (r.has_file ? '' : ' (미업로드)') : '파일 없음')
