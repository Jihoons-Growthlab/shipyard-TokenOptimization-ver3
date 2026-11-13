<template>
  <AppModal :title="`도면 ${d?.drawing_no || ''}`" size="xl" @close="$emit('close')">
    <div v-if="d" class="dd">
      <section class="card viewer">
        <h3>도면 뷰어 (PDF) <small class="muted">작성중(DRAFT) 리비전만 업로드·교체·삭제할 수 있습니다.</small></h3>
        <div class="vtool">
          <select v-model.number="viewRev" class="rsel" aria-label="리비전">
            <option v-for="r in d.revisions" :key="r.rev_no" :value="r.rev_no">Rev{{ r.rev_no }} ({{ codeName('DWGSTAT', r.rev_status) }})</option>
          </select>
          <span class="vname">{{ cur?.file_nm || '파일 없음' }}</span>
          <span class="b" :class="cur?.has_file ? 'b-ok' : 'b-warn'">{{ cur?.has_file ? '업로드 파일' : '샘플 PDF (미업로드)' }}</span>
          <div class="grow"></div>
          <input v-if="canWrite" :key="'up' + upKey" type="file" class="vfile" name="pdf" accept=".pdf,application/pdf"
            :disabled="!isDraft || busy" @change="onUpload" />
          <button v-if="canWrite" class="btn" type="button" :disabled="!(isDraft && cur?.has_file) || busy" @click="deletePdf">파일 삭제</button>
          <button class="btn" type="button" @click="openWindow">새 창으로 열기</button>
        </div>
        <div class="vbody">
          <iframe v-if="pdfUrl" :src="pdfUrl + '#view=FitH'" title="도면 PDF"></iframe>
          <div v-else class="sample">
            <b>샘플 PDF (미업로드)</b>
            <span>{{ d.drawing_no }} · Rev{{ cur?.rev_no }} · {{ codeName('DWGSTAT', cur?.rev_status) }}</span>
            <small>이 리비전에는 업로드된 도면 파일이 없습니다.</small>
          </div>
        </div>
      </section>

      <div class="side">
        <p class="meta">{{ d.hull_no }} · {{ codeName('DWGDISC', d.discipline) }} · {{ d.drawing_nm }}</p>
        <section class="card">
          <h3>도면 정보</h3>
          <form @submit.prevent="save">
            <DrawingFields :model="form" :hulls="hulls" :users="users" :current="d" edit :readonly="!canWrite" />
            <div v-if="canWrite" class="bar-row">
              <button class="btn pri" type="submit" :disabled="busy">저장</button>
              <button class="btn danger" type="button" :disabled="busy" @click="remove">삭제</button>
            </div>
          </form>
        </section>

        <section class="card">
          <h3>리비전 이력 <span class="b cnt">{{ d.revisions.length }}</span></h3>
          <div class="tw rv">
            <table class="t fixed rev-table">
              <colgroup><col style="width: 92px" /><col style="width: 62px" /><col /><col style="width: 92px" /></colgroup>
              <thead><tr><th>Rev</th><th>상태</th><th>변경사유</th><th>배포일</th></tr></thead>
              <tbody>
                <tr v-for="r in d.revisions" :key="r.rev_no" :class="{ on: r.rev_no === viewRev }">
                  <td><b>Rev{{ r.rev_no }}</b> <a class="lnk" href="#" @click.prevent="viewRev = r.rev_no">보기</a></td>
                  <td><StatusBadge group="DWGSTAT" :code="r.rev_status" /></td>
                  <td class="wrap"><div class="ell" :title="r.change_desc">{{ r.change_desc }}</div><div class="fn ell" :title="fileLine(r)">{{ fileLine(r) }}</div></td>
                  <td class="wrap">{{ r.issue_dt || '미배포' }}<div class="fn">{{ r.author_nm }}</div></td>
                </tr>
              </tbody>
            </table>
          </div>
          <template v-if="canWrite && latest">
            <div v-if="['ISSUED', 'OBSOLETE'].includes(latest.rev_status)" class="fg c2 act">
              <label class="f sall"><span>신규 Rev{{ latest.rev_no + 1 }} 개정 사유</span><input v-model.trim="nr.desc" name="change_desc" /></label>
              <label class="f"><span>도면 파일 (PDF, 선택)</span>
                <input :key="'nr' + nr.key" type="file" accept=".pdf,application/pdf" @change="nr.file = $event.target.files[0] || null" />
              </label>
              <div><button class="btn pri" type="button" :disabled="busy" @click="createRev">신규 Rev 작성</button></div>
            </div>
            <template v-else-if="latest.rev_status === 'DRAFT'">
              <div class="note warn act">Rev{{ latest.rev_no }} 작성중입니다. 검토자/승인자를 지정해 결재를 요청하세요.</div>
              <div class="fg c2 act">
                <label class="f"><span>1단계 검토자</span>
                  <select v-model="req.reviewer" name="reviewer"><option value="">선택</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ userLabel(u) }}</option></select>
                </label>
                <label class="f"><span>2단계 승인자</span>
                  <select v-model="req.approver" name="approver"><option value="">선택</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ userLabel(u) }}</option></select>
                </label>
                <div><button class="btn pri" type="button" :disabled="busy" @click="requestApproval">결재 요청</button></div>
              </div>
            </template>
            <div v-else-if="latest.rev_status === 'REVIEW'" class="note warn act">Rev{{ latest.rev_no }} 결재 진행중입니다. 결재자는 [결재함]에서 처리합니다.</div>
            <template v-else-if="latest.rev_status === 'APPROVED'">
              <div class="note ok act">Rev{{ latest.rev_no }} 승인 완료 — 배포하면 연계 공정의 도면 게이트가 열립니다.</div>
              <div class="bar-row"><button class="btn ok" type="button" :disabled="busy" @click="issue">Rev{{ latest.rev_no }} 배포</button></div>
            </template>
          </template>
        </section>

        <section class="card">
          <h3>결재 이력</h3>
          <div class="tw">
            <table class="t">
              <thead><tr><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th></tr></thead>
              <tbody>
                <tr v-for="a in d.approvals" :key="a.approval_id" :title="[a.comment, a.act_dt].filter(Boolean).join(' · ')">
                  <td>Rev{{ a.rev_no }}</td><td>{{ STEP_NM[a.step_no] }}</td><td>{{ a.approver_nm || '-' }}</td>
                  <td><span class="b" :class="RESULT_BADGE[a.result]?.[1]">{{ RESULT_BADGE[a.result]?.[0] || a.result }}</span></td>
                </tr>
                <tr v-if="!d.approvals.length"><td colspan="4" class="empty">결재 이력이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card">
          <h3>연계 공정 <span class="b cnt">{{ d.plans.length }}</span></h3>
          <div v-if="d.impacts.length" class="note warn imp">
            ⚠ 최근 개정(Rev{{ d.impacts[0].rev_no }}, {{ d.impacts[0].issue_dt }})으로 이미 착수·완료된 공정 {{ d.impacts.length }}건이 영향을 받습니다: {{ d.impacts.map((i) => i.plan_label).join(', ') }}
          </div>
          <div class="tw">
            <table class="t">
              <thead><tr><th>공정</th><th>상태</th><th>구분</th><th>필요일</th><th v-if="canWrite"></th></tr></thead>
              <tbody>
                <tr v-for="p in d.plans" :key="p.plan_id">
                  <td><a class="lnk" href="#" @click.prevent="goPlan">{{ p.label }}</a></td>
                  <td><StatusBadge :code="p.plan_status" /></td>
                  <td>{{ p.required ? '필수' : '참고' }}</td>
                  <td>{{ p.need_dt || '-' }}</td>
                  <td v-if="canWrite"><button class="btn sm" type="button" :disabled="busy" @click="unlink(p)">해제</button></td>
                </tr>
                <tr v-if="!d.plans.length"><td :colspan="canWrite ? 5 : 4" class="empty">연계된 공정이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
          <div v-if="canWrite" class="bar-row">
            <select v-model="lk.plan_id" class="psel" aria-label="연계 공정">
              <option value="">공정 선택</option>
              <option v-for="p in d.available_plans" :key="p.plan_id" :value="p.plan_id">{{ p.label }}</option>
            </select>
            <label class="chk"><input v-model="lk.required" type="checkbox" />필수</label>
            <button class="btn" type="button" :disabled="busy" @click="addLink">+ 공정 연계</button>
          </div>
        </section>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import { computed, inject, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import { codeName, fail, toast, userLabel } from '../stores/session.js'
import { checkPdf, fileLine, loadHullOptions, RESULT_BADGE, STEP_NM, uploadPdf } from '../utils/drawing.js'
import AppModal from '../components/AppModal.vue'
import DrawingFields from '../components/DrawingFields.vue'
import StatusBadge from '../components/StatusBadge.vue'

const props = defineProps({ drawingId: { type: Number, required: true }, canWrite: Boolean })
const emit = defineEmits(['close', 'changed'])
const navigate = inject('navigate', () => {})

const d = ref(null)
const viewRev = ref(null)
const pdfUrl = ref('')
const busy = ref(false)
const upKey = ref(0)
const form = reactive({})
const hulls = ref([])
const users = ref([])
const nr = reactive({ desc: '', file: null, key: 0 })
const req = reactive({ reviewer: '', approver: '' })
const lk = reactive({ plan_id: '', required: true })

const cur = computed(() => d.value?.revisions.find((r) => r.rev_no === viewRev.value) || null)
const latest = computed(() => d.value?.revisions[0] || null)
const isDraft = computed(() => cur.value?.rev_status === 'DRAFT')
const base = () => `/api/drawings/${props.drawingId}`

function apply(x, rev = viewRev.value) {
  d.value = x
  Object.assign(form, {
    drawing_no: x.drawing_no, drawing_nm: x.drawing_nm, discipline: x.discipline,
    hull_no: x.hull_no, block_id: x.block_id, designer_emp_no: x.designer_emp_no,
  })
  viewRev.value = x.revisions.some((r) => r.rev_no === rev) ? rev : (x.revisions[0]?.rev_no ?? null)
  if (!x.available_plans.some((p) => p.plan_id === lk.plan_id)) lk.plan_id = ''
}
async function load(rev) {
  try { apply(await api.get(base()), rev) } catch (e) { fail(e) }
}

// 뷰어: 인증 fetch → blob URL. 이전 URL은 해제하고 늦은 응답은 버린다.
let pdfSeq = 0
function revoke() {
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value)
  pdfUrl.value = ''
}
async function loadPdf() {
  const seq = ++pdfSeq
  revoke()
  const r = cur.value
  if (!r?.has_file) return
  try {
    const blob = await api.blob(`${base()}/revisions/${r.rev_no}/pdf`)
    if (seq === pdfSeq) pdfUrl.value = URL.createObjectURL(blob)
  } catch (e) { if (seq === pdfSeq) fail(e) }
}
watch(() => [viewRev.value, cur.value?.has_file, cur.value?.file_nm, d.value], loadPdf)

function openWindow() {
  if (!pdfUrl.value) return toast('표시 중인 PDF가 없습니다.', 'error')
  window.open(pdfUrl.value, '_blank')
}

/** 쓰기 요청 공통: 처리 중 비활성, 성공 토스트, 목록 갱신 알림. 실패 시 undefined. */
async function run(fn, msg) {
  busy.value = true
  try {
    const res = await fn()
    if (msg) toast(msg, 'success')
    emit('changed')
    return res ?? true
  } catch (e) {
    fail(e)
    return undefined
  } finally { busy.value = false }
}

async function onUpload(e) {
  const file = e.target.files?.[0]
  upKey.value++
  if (!file || !cur.value) return
  const err = await checkPdf(file)
  if (err) return toast(err, 'error')
  const n = cur.value.rev_no
  await run(() => uploadPdf(props.drawingId, n, file), `Rev${n}에 PDF를 업로드했습니다.`)
  await load(n)
}
async function deletePdf() {
  const n = cur.value.rev_no
  if (await run(() => api.del(`${base()}/revisions/${n}/pdf`), '파일을 삭제했습니다.')) await load(n)
}
async function save() {
  const { drawing_nm, discipline, block_id, designer_emp_no } = form
  const x = await run(() => api.patch(base(), { drawing_nm, discipline, block_id, designer_emp_no }), '저장되었습니다.')
  if (x && x !== true) apply(x)
}
async function remove() {
  if (!window.confirm('도면과 리비전·결재·공정 연계를 삭제합니다.')) return
  if (await run(() => api.del(base()), '삭제되었습니다.')) emit('close')
}
async function createRev() {
  const file = nr.file
  if (file) {
    const err = await checkPdf(file)
    if (err) return toast(err, 'error')
  }
  const n = latest.value.rev_no + 1
  if (!(await run(() => api.post(`${base()}/revisions`, { change_desc: nr.desc }), `Rev${n} 작성중으로 생성되었습니다.`))) return
  if (file) {
    try {
      await uploadPdf(props.drawingId, n, file)
      toast(`Rev${n}에 PDF를 업로드했습니다.`, 'success')
    } catch (e) { fail(e) }
  }
  Object.assign(nr, { desc: '', file: null, key: nr.key + 1 })
  await load(n)
}
async function requestApproval() {
  const n = latest.value.rev_no
  const body = { reviewer_emp_no: req.reviewer || null, approver_emp_no: req.approver || null }
  if (await run(() => api.post(`${base()}/revisions/${n}/request-approval`, body), '결재가 요청되었습니다.')) await load(n)
}
async function issue() {
  const n = latest.value.rev_no
  if (await run(() => api.post(`${base()}/revisions/${n}/issue`), '도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')) await load(n)
}
async function addLink() {
  if (!lk.plan_id) return toast('공정을 선택하세요.', 'error')
  if (await run(() => api.post(`${base()}/plans`, { plan_id: Number(lk.plan_id), required: lk.required }), '공정이 연계되었습니다.')) {
    lk.plan_id = ''
    await load()
  }
}
async function unlink(p) {
  if (await run(() => api.del(`${base()}/plans/${p.plan_id}`), '연계가 해제되었습니다.')) await load()
}
function goPlan() {
  navigate('plan-gantt', d.value.hull_no)
  emit('close')
}

onMounted(async () => {
  const [, h, u] = await Promise.all([load(), loadHullOptions().catch(() => []), api.get('/api/users/options').catch(() => [])])
  hulls.value = h
  users.value = u
  const has = (id) => u.some((x) => x.emp_no === id)
  Object.assign(req, { reviewer: has('lee.dwg') ? 'lee.dwg' : '', approver: has('admin') ? 'admin' : '' })
})
onUnmounted(() => { pdfSeq++; revoke() })
</script>

<style scoped>
.dd { display: grid; grid-template-columns: minmax(0, 1fr) 440px; gap: 12px; height: 100%; min-height: 0; }
.viewer { display: flex; flex-direction: column; margin: 0; min-height: 0; }
.viewer h3 small { font-size: 12px; font-weight: 400; }
.vtool { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.vtool .grow { flex: 1; }
.rsel { width: 110px; }
.vfile { width: 230px; }
.vbody { flex: 1; min-height: 0; background: #525659; border-radius: 4px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.vbody iframe { width: 100%; height: 100%; border: 0; background: #525659; }
.sample { color: #fff; text-align: center; display: flex; flex-direction: column; gap: 8px; }
.sample small { font-size: 11.5px; }
.side { overflow: auto; min-height: 0; }
.meta { margin: 0 0 8px; font-size: 12px; color: var(--muted); }
.cnt { background: #e5e7eb; color: #4b5563; font-weight: 400; }
.rv { max-height: 190px; }
.t.fixed { table-layout: fixed; }
.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fn { font-size: 11.5px; color: var(--muted); }
.act { margin-top: 10px; }
.imp { margin-bottom: 8px; }
.psel { flex: 1; }
@media (max-width: 1100px) {
  .dd { grid-template-columns: 1fr; height: auto; }
  .viewer { height: 60vh; }
  .side { overflow: visible; }
}
</style>
