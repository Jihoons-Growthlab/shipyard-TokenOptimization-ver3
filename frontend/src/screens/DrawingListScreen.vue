<template>
  <div>
    <PageHead title="도면 목록" desc="행에 마우스를 올리면 정보·PDF 미리보기가 뜹니다. 행 더블클릭 또는 [상세]로 도면 상세·PDF 뷰어·리비전·결재 팝업을 엽니다. Rev는 현재 배포(유효) 리비전입니다." :readonly="!canWrite" />
    <form class="toolbar" @submit.prevent="load">
      <select v-model="f.hull_no" class="hsel" aria-label="호선">
        <option value="">호선 전체</option>
        <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
      <select v-model="f.discipline" class="dsel" aria-label="분야">
        <option value="">분야 전체</option>
        <option v-for="c in codeList('DWGDISC')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <select v-model="f.status" class="dsel" aria-label="상태">
        <option value="">상태 전체</option>
        <option v-for="c in codeList('DWGSTAT')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <input v-model.trim="f.q" class="fq" placeholder="도면번호/도면명" />
      <button class="btn pri" type="submit">조회</button>
      <button class="btn" type="button" @click="resetFilter">초기화</button>
      <div class="grow"></div>
      <button v-if="canWrite" class="btn pri" type="button" @click="openNew">+ 도면 등록</button>
    </form>
    <div class="tw">
      <table class="t dwg-table">
        <thead>
          <tr><th>도면번호</th><th>도면명</th><th>호선</th><th>블록</th><th>분야</th><th>Rev</th><th>상태</th><th>설계자</th><th class="num">연계공정</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="x in list" :key="x.drawing_id" class="click" :class="{ on: selected === x.drawing_id }"
            @click="selected = x.drawing_id" @dblclick="openDetail(x.drawing_id)"
            @mouseenter="hp.enter(x.drawing_id, $event)" @mouseleave="hp.leave">
            <td><b>{{ x.drawing_no }}</b></td>
            <td>{{ x.drawing_nm }}</td>
            <td>{{ x.hull_no }}</td>
            <td>{{ x.block_cd || '-' }}</td>
            <td>{{ codeName('DWGDISC', x.discipline) }}</td>
            <td>{{ revText(x).cur }}<span class="muted">{{ revText(x).latest }}</span></td>
            <td><StatusBadge group="DWGSTAT" :code="x.dwg_status" /></td>
            <td>{{ x.designer_nm || '-' }}</td>
            <td class="num">{{ x.link_count || '-' }}</td>
            <td><button class="btn sm" type="button" @click.stop="openDetail(x.drawing_id)">상세</button></td>
          </tr>
          <tr v-if="loaded && !list.length"><td colspan="10" class="empty">조회된 도면이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="total">총 {{ list.length }}건</div>

    <AppModal v-if="creating" title="도면 등록" size="large" @close="creating = false">
      <p class="mdesc">신규 도면은 Rev0(작성중)으로 생성됩니다. PDF는 지금 첨부하거나 등록 후 뷰어에서 업로드할 수 있습니다.</p>
      <form class="card" @submit.prevent="create">
        <DrawingFields :model="nf" :hulls="hulls" :users="users">
          <label class="f s2"><span>도면 파일 (PDF, 선택)</span>
            <input type="file" name="file" accept=".pdf,application/pdf" @change="nfFile = $event.target.files[0] || null" />
          </label>
        </DrawingFields>
        <div class="bar-row"><button class="btn pri" type="submit" :disabled="busy">저장</button></div>
      </form>
    </AppModal>
    <HoverCard v-if="hp.pv.key && !detailId" :pos="hp.pv.pos" :width="440" :height="470" @enter="hp.keep" @leave="hp.leave">
      <p v-if="hp.pv.error" class="muted">{{ hp.pv.error }}</p>
      <p v-else-if="!hp.pv.data" class="muted">불러오는 중…</p>
      <div v-else class="pv" @click="openDetail(hp.pv.key)">
        <template v-for="d in [hp.pv.data.d]" :key="d.drawing_id">
          <div class="pvh"><b>{{ d.drawing_no }}</b><StatusBadge group="DWGSTAT" :code="d.dwg_status" /></div>
          <div class="pvm">{{ d.drawing_nm }}</div>
          <div class="pvm">{{ d.hull_no }} · {{ d.block_cd ? `${d.block_cd} ${d.block_nm || ''}` : '블록 없음' }} · {{ codeName('DWGDISC', d.discipline) }} · 설계 {{ d.designer_nm || '-' }}</div>
          <div class="pvpdf">
            <div v-if="hp.pv.data.pdf && !pdfViewer" class="nopdf muted">
              이 브라우저는 PDF를 화면에 표시하지 않도록 설정되어 있습니다.
              <a class="lnk" :href="hp.pv.data.pdf" target="_blank" rel="noopener" @click.stop>PDF 열기</a>
            </div>
            <iframe v-else-if="hp.pv.data.pdf" :key="hp.pv.data.pdf" :src="hp.pv.data.pdf + '#toolbar=0&navpanes=0&view=FitH'" :title="`${d.drawing_no} 미리보기`" tabindex="-1"></iframe>
            <div v-else class="nopdf muted">첨부된 PDF가 없습니다.</div>
            <span v-if="hp.pv.data.rev" class="pvrev">Rev{{ hp.pv.data.rev.rev_no }} · {{ codeName('DWGSTAT', hp.pv.data.rev.rev_status) }}</span>
          </div>
          <table class="pvt">
            <thead><tr><th>Rev</th><th>상태</th><th>변경 내용</th><th>배포일</th></tr></thead>
            <tbody>
              <tr v-for="r in d.revisions.slice(0, 3)" :key="r.rev_no"><td>Rev{{ r.rev_no }}</td><td><StatusBadge group="DWGSTAT" :code="r.rev_status" /></td><td class="ell">{{ r.change_desc || '-' }}</td><td>{{ r.issue_dt || '-' }}</td></tr>
            </tbody>
          </table>
          <div class="pvf muted">연계 공정 {{ d.plans.length }}건 · 클릭하면 상세를 엽니다.</div>
        </template>
      </div>
    </HoverCard>
    <DrawingDetail v-if="detailId" :key="detailId" :drawing-id="detailId" :can-write="canWrite" @close="detailId = null" @changed="load" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import { codeList, codeName, fail, session, toast } from '../stores/session.js'
import { checkPdf, loadHullOptions, revText, uploadPdf } from '../utils/drawing.js'
import PageHead from '../components/PageHead.vue'
import AppModal from '../components/AppModal.vue'
import StatusBadge from '../components/StatusBadge.vue'
import DrawingFields from '../components/DrawingFields.vue'
import DrawingDetail from './DrawingDetail.vue'
import HoverCard from '../components/HoverCard.vue'
import { useHoverPreview } from '../utils/hoverPreview.js'

const props = defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const f = reactive({ hull_no: '', discipline: '', status: '', q: '' })
const list = ref([])
const loaded = ref(false)
const selected = ref(null)
const hulls = ref([])
const users = ref([])
const detailId = ref(null)
const creating = ref(false)
const busy = ref(false)
const nf = reactive({})
const nfFile = ref(null)

async function load() {
  try {
    list.value = await api.get('/api/drawings', { ...f })
    hp.clear()
    loaded.value = true
  } catch (e) { fail(e) }
}
function resetFilter() {
  Object.assign(f, { hull_no: '', discipline: '', status: '', q: '' })
  load()
}
// 미리보기 PDF: 현재(배포) 리비전에 파일이 있으면 그것, 없으면 파일이 있는 최신 리비전.
const hp = useHoverPreview(async (id) => {
  const d = await api.get(`/api/drawings/${id}`)
  const rev = d.revisions.find((r) => r.rev_no === d.current_rev_no && r.has_file) || d.revisions.find((r) => r.has_file) || null
  const pdf = rev ? URL.createObjectURL(await api.blob(`/api/drawings/${id}/revisions/${rev.rev_no}/pdf`)) : ''
  return { d, rev, pdf }
}, { onDispose: (v) => v.pdf && URL.revokeObjectURL(v.pdf) })
// Chrome에서 'PDF를 다운로드' 설정이면 iframe 미리보기가 빈칸(또는 다운로드)이 된다.
const pdfViewer = typeof navigator === 'undefined' || navigator.pdfViewerEnabled !== false
function openDetail(id) {
  hp.close()
  selected.value = id
  detailId.value = id
}
function openNew() {
  Object.assign(nf, {
    drawing_no: '', drawing_nm: '', discipline: codeList('DWGDISC')[0]?.code ?? null,
    hull_no: hulls.value[0]?.hull_no ?? null, block_id: null, designer_emp_no: session.me?.emp_no ?? null,
  })
  nfFile.value = null
  creating.value = true
}
async function create() {
  const file = nfFile.value
  if (file) {
    const err = await checkPdf(file)
    if (err) return toast(err, 'error')
  }
  busy.value = true
  try {
    const d = await api.post('/api/drawings', { ...nf })
    let msg = '도면이 등록되었습니다. (Rev0 작성중)'
    if (file) {
      try {
        await uploadPdf(d.drawing_id, 0, file)
        msg += ' PDF 첨부됨.'
      } catch (e) { msg += ` (PDF 저장 실패: ${e.message})` }
    }
    toast(msg, 'success')
    creating.value = false
    await load()
    openDetail(d.drawing_id)
  } catch (e) { fail(e) } finally { busy.value = false }
}
function applyParam() {
  if (props.param) f.hull_no = String(props.param)
  load()
}
watch(() => props.ctx, applyParam)

onMounted(async () => {
  applyParam()
  const [h, u] = await Promise.all([loadHullOptions().catch(() => []), api.get('/api/users/options').catch(() => [])])
  hulls.value = h
  users.value = u
})
</script>

<style scoped>
.hsel { width: 166px; }
.dsel { width: 110px; }
.fq { width: 148px; }
.total { margin-top: 8px; font-size: 12px; color: var(--muted); }
.mdesc { margin: 0 0 10px; font-size: 12px; color: var(--muted); }
</style>
