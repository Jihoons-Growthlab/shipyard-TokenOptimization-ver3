<template>
  <AppModal :title="no ? `호선 ${no}` : '호선 등록'" :size="tab === 'viewer' ? 'xl' : 'large'" @close="emit('close')">
    <p class="mdesc">{{ no ? codeName('HULLSTAT', hull?.hull_status) : '신규 호선을 등록합니다.' }}</p>
    <div v-if="no" class="subtabs">
      <button v-for="s in SUBTABS" :key="s.id" type="button" :class="{ on: tab === s.id }" @click="switchTab(s.id)">{{ s.label }}</button>
    </div>

    <!-- 기본정보 -->
    <form v-if="tab === 'info'" class="card" @submit.prevent="saveInfo">
      <fieldset class="fs" :disabled="loading">
        <div class="fg c4">
          <label class="f"><span>호선번호 *</span><input v-model.trim="form.hull_no" name="hull_no" :readonly="!!no" /></label>
          <label class="f s2"><span>호선명</span><input v-model="form.hull_nm" name="hull_nm" /></label>
          <label class="f"><span>선종</span>
            <select v-model="form.ship_type" name="ship_type"><option value="">선택</option><option v-for="c in codeList('SHIPTYPE')" :key="c.code" :value="c.code">{{ c.name }}</option></select>
          </label>
          <label class="f"><span>상태</span>
            <select v-model="form.hull_status" name="hull_status"><option value="">선택</option><option v-for="c in codeList('HULLSTAT')" :key="c.code" :value="c.code">{{ c.name }}</option></select>
          </label>
          <label class="f s2"><span>선주</span><input v-model="form.owner_nm" name="owner_nm" /></label>
          <label class="f"><span>선급</span><input v-model="form.class_society" name="class_society" /></label>
          <label class="f"><span>전장(m)</span><input v-model="form.length_m" type="number" step="any" min="0" /></label>
          <label class="f"><span>선폭(m)</span><input v-model="form.breadth_m" type="number" step="any" min="0" /></label>
          <label class="f"><span>선심(m)</span><input v-model="form.depth_m" type="number" step="any" min="0" /></label>
          <label class="f"><span>재화중량(DWT)</span><input v-model="form.dead_weight" type="number" step="any" min="0" /></label>
          <label class="f"><span>도크/건조장소</span><input v-model="form.dock_no" /></label>
          <label class="f"><span>계약일</span><input v-model="form.contract_dt" type="date" /></label>
          <label class="f"><span>인도 예정일</span><input v-model="form.delivery_dt" type="date" /></label>
          <div class="f"><span>사용여부</span><label class="chk"><input v-model="form.use_yn" type="checkbox" />사용</label></div>
          <label class="f sall"><span>비고</span><input v-model="form.remark" /></label>
        </div>
      </fieldset>
      <div class="bar-row">
        <button class="btn pri" type="submit" :disabled="!canWrite || loading">저장</button>
        <button v-if="no" class="btn danger" type="button" :disabled="!canWrite || loading" @click="removeHull">삭제</button>
        <span class="muted">삭제 시 블록·공정·도면이 함께 삭제됩니다(FK CASCADE).</span>
      </div>
    </form>

    <!-- 주요일정 -->
    <div v-else-if="tab === 'milestones'" class="card">
      <div class="tw">
        <table class="t">
          <thead><tr><th>일정</th><th>계획일</th><th>실적일</th><th class="num">차이(일)</th></tr></thead>
          <tbody>
            <tr v-for="m in milestones" :key="m.milestone_cd">
              <td>{{ m.name }}</td>
              <td><input v-model="m.plan_dt" type="date" :disabled="loading" /></td>
              <td><input v-model="m.actual_dt" type="date" :disabled="loading" /></td>
              <td class="num">{{ m.plan_dt && m.actual_dt ? diffDays(m.actual_dt, m.plan_dt) : '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="bar-row"><button class="btn pri" type="button" :disabled="!canWrite || loading" @click="saveMilestones">일정 저장</button></div>
    </div>

    <!-- 블록 구성 -->
    <div v-else-if="tab === 'blocks'" class="card">
      <div class="tw">
        <table class="t">
          <thead><tr><th>블록코드</th><th>블록명</th><th>유형</th><th class="num">중량(ton)</th><th>진척</th><th class="num">공정</th><th class="num">도면</th><th></th></tr></thead>
          <tbody>
            <tr v-for="b in blocks" :key="b.block_id">
              <td><b>{{ b.block_cd }}</b></td>
              <td>{{ b.block_nm }}</td>
              <td>{{ codeName('BLOCKTYPE', b.block_type) }}</td>
              <td class="num">{{ dash(b.weight_ton) }}</td>
              <td class="pcell"><ProgressBar v-if="b.progress !== null" :value="b.progress" /><span v-else>-</span></td>
              <td class="num">{{ b.plan_count }}</td>
              <td class="num">{{ b.drawing_count }}</td>
              <td><button class="btn sm danger" type="button" :disabled="!canWrite" @click="removeBlock(b)">삭제</button></td>
            </tr>
            <tr v-if="!loading && !blocks.length"><td colspan="8" class="empty">블록이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
      <form class="addrow" @submit.prevent="addBlock">
        <input v-model.trim="nb.block_cd" placeholder="블록코드 *" :disabled="!canWrite" />
        <input v-model="nb.block_nm" placeholder="블록명" :disabled="!canWrite" />
        <select v-model="nb.block_type" :disabled="!canWrite"><option value="">유형 선택</option><option v-for="c in codeList('BLOCKTYPE')" :key="c.code" :value="c.code">{{ c.name }}</option></select>
        <input v-model="nb.weight_ton" type="number" step="any" min="0" placeholder="중량(ton)" :disabled="!canWrite" />
        <button class="btn pri" type="submit" :disabled="!canWrite">+ 블록 추가</button>
      </form>
    </div>

    <!-- 3D 보기: 탭에 들어갈 때 시작, 떠나면 종료 -->
    <ShipViewer3D v-else-if="tab === 'viewer'" />

    <!-- 연계 현황 -->
    <div v-else-if="tab === 'summary'" class="sum">
      <div class="card">
        <h4>공정 <button class="btn sm" type="button" @click="go('plan-gantt')">간트 보기</button></h4>
        <template v-if="summary?.plan_count">
          <p>전체 진척 {{ summary.progress ?? 0 }}%</p>
          <ul><li v-for="c in codeList('PLANSTAT')" :key="c.code">{{ c.name }}: {{ summary.plan_status[c.code] ?? 0 }}</li></ul>
        </template>
        <p v-else-if="summary" class="muted">공정 계획이 없습니다.</p>
      </div>
      <div class="card">
        <h4>도면 <button class="btn sm" type="button" @click="go('dwg-list')">목록 보기</button></h4>
        <ul v-if="summary?.drawing_count">
          <li v-for="k in DWG_KEYS" :key="k">{{ codeName('DWGSTAT', k) }}: {{ summary.drawing_status[k] ?? 0 }}</li>
        </ul>
        <p v-else-if="summary" class="muted">도면이 없습니다.</p>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import { inject, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import { codeList, codeName, fail, toast } from '../stores/session.js'
import { blankNull, dash, diffDays, numOrNull } from '../utils/date.js'
import AppModal from '../components/AppModal.vue'
import ProgressBar from '../components/ProgressBar.vue'
import ShipViewer3D from '../components/ShipViewer3D.vue'

const props = defineProps({ hullNo: { type: String, default: null }, canWrite: Boolean })
const emit = defineEmits(['close', 'changed'])
const navigate = inject('navigate')

const SUBTABS = [
  { id: 'info', label: '기본정보' },
  { id: 'milestones', label: '주요일정' },
  { id: 'blocks', label: '블록 구성' },
  { id: 'summary', label: '연계 현황' },
  { id: 'viewer', label: '3D 보기' },
]
const DWG_KEYS = ['ISSUED', 'APPROVED', 'REVIEW', 'DRAFT']
const NUM_FIELDS = ['length_m', 'breadth_m', 'depth_m', 'dead_weight']
const TEXT_FIELDS = ['hull_nm', 'ship_type', 'hull_status', 'owner_nm', 'class_society', 'dock_no', 'contract_dt', 'delivery_dt', 'remark']

const no = ref(props.hullNo)
const tab = ref('info')
const loading = ref(false)
const hull = ref(null)
const blankForm = () => ({ hull_no: '', hull_nm: '', ship_type: '', hull_status: 'PLAN', owner_nm: '', class_society: '', length_m: '', breadth_m: '', depth_m: '', dead_weight: '', dock_no: '', contract_dt: '', delivery_dt: '', use_yn: true, remark: '' })
const form = reactive(blankForm())
const milestones = ref([])
const blocks = ref([])
const summary = ref(null)
const blankBlock = () => ({ block_cd: '', block_nm: '', block_type: '', weight_ton: '' })
const nb = reactive(blankBlock())

function fillForm(h) {
  Object.assign(form, blankForm())
  for (const k of Object.keys(form)) if (h[k] !== null && h[k] !== undefined) form[k] = h[k]
}

const loaders = {
  info: async () => { hull.value = await api.get(`/api/hulls/${no.value}`); fillForm(hull.value) },
  milestones: async () => { milestones.value = await api.get(`/api/hulls/${no.value}/milestones`) },
  blocks: async () => { blocks.value = await api.get(`/api/hulls/${no.value}/blocks`) },
  summary: async () => { summary.value = await api.get(`/api/hulls/${no.value}/summary`) },
}

async function load() {
  if (!no.value) return
  loading.value = true
  try {
    const tasks = [loaders[tab.value]()]
    if (tab.value !== 'info') tasks.push(api.get(`/api/hulls/${no.value}`).then((h) => { hull.value = h }))
    await Promise.all(tasks)
  } catch (e) { fail(e) } finally { loading.value = false }
}

// 3D 탭 왕복은 작성 중 내용을 유지한다(데이터 탭 간 이동은 재조회).
let lastDataTab = 'info'
function switchTab(id) {
  if (id === tab.value) return
  tab.value = id
  if (id === 'viewer') return
  const same = id === lastDataTab
  lastDataTab = id
  if (!same) load()
}

function payload() {
  const body = { use_yn: !!form.use_yn }
  for (const k of TEXT_FIELDS) body[k] = blankNull(typeof form[k] === 'string' ? form[k].trim() : form[k])
  for (const k of NUM_FIELDS) body[k] = numOrNull(form[k])
  return body
}

async function saveInfo() {
  try {
    if (no.value) {
      await api.patch(`/api/hulls/${no.value}`, payload())
      toast('저장되었습니다.', 'success')
    } else {
      const created = await api.post('/api/hulls', { hull_no: form.hull_no, ...payload() })
      no.value = created.hull_no
      toast('호선이 등록되었습니다.', 'success')
    }
    emit('changed')
    await load()
  } catch (e) { fail(e) }
}

async function removeHull() {
  if (!confirm(`호선 ${no.value} 및 하위 데이터(블록·공정·도면)를 모두 삭제합니다. 계속할까요?`)) return
  try {
    await api.del(`/api/hulls/${no.value}`)
    toast('삭제되었습니다.', 'success')
    emit('changed')
    emit('close')
  } catch (e) { fail(e) }
}

async function saveMilestones() {
  try {
    const items = milestones.value.map((m) => ({ milestone_cd: m.milestone_cd, plan_dt: blankNull(m.plan_dt), actual_dt: blankNull(m.actual_dt) }))
    milestones.value = await api.put(`/api/hulls/${no.value}/milestones`, { items })
    toast('주요일정이 저장되었습니다.', 'success')
    emit('changed')
  } catch (e) { fail(e) }
}

async function addBlock() {
  try {
    await api.post(`/api/hulls/${no.value}/blocks`, { block_cd: nb.block_cd, block_nm: blankNull(nb.block_nm), block_type: blankNull(nb.block_type), weight_ton: numOrNull(nb.weight_ton) })
    Object.assign(nb, blankBlock())
    toast('블록이 추가되었습니다.', 'success')
    await load()
  } catch (e) { fail(e) }
}

async function removeBlock(b) {
  if (!confirm('블록과 해당 블록의 공정을 삭제합니다. (도면의 블록 연결은 해제)')) return
  try {
    await api.del(`/api/blocks/${b.block_id}`)
    toast('삭제되었습니다.', 'success')
    emit('changed')
    await load()
  } catch (e) { fail(e) }
}

function go(token) {
  const target = no.value
  emit('close')
  navigate(token, target)
}

onMounted(load)
</script>

<style scoped>
.mdesc { margin: 0 0 10px; font-size: 12px; color: var(--muted); }
.fs { border: 0; padding: 0; margin: 0; min-width: 0; }
.pcell { width: 200px; }
.addrow { display: flex; gap: 8px; margin-top: 12px; }
.addrow input, .addrow select { width: 148px; }
.addrow select { width: 110px; }
.sum { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.sum .card { min-height: 205px; padding-top: 28px; }
.sum h4 { display: flex; align-items: center; gap: 6px; font-size: 13px; margin: 0 0 16px; }
.sum p { margin: 0 0 8px; }
.sum ul { margin: 0; padding-left: 40px; line-height: 1.25; }
</style>
