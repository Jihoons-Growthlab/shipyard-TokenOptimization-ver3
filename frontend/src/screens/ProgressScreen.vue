<template>
  <div>
    <PageHead title="공정 실적 입력" desc="착수 가능/진행/지연 공정의 일별 진척률·공수를 입력하면 공정 진척과 상태가 갱신됩니다." :readonly="!canWrite" />
    <div class="toolbar">
      <select v-model="hullNo" class="hsel" aria-label="호선" @change="changeHull">
        <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
      <label class="chk"><input v-model="includeDone" type="checkbox" @change="loadTargets" />완료 공정 포함</label>
    </div>
    <div class="tw">
      <table class="t prog-table">
        <thead><tr><th>공정</th><th>계획기간</th><th>실제착수</th><th>진척</th><th>상태</th><th>담당</th></tr></thead>
        <tbody>
          <tr v-for="p in targets" :key="p.plan_id" class="click" :class="{ on: p.plan_id === selectedId }" @click="select(p)"
            @mouseenter="preview.enter(p.plan_id, $event)" @mouseleave="preview.leave">
            <td>{{ p.label }}</td>
            <td>{{ p.plan_start_dt }} ~ {{ p.plan_end_dt }}</td>
            <td>{{ dash(p.actual_start_dt) }}</td>
            <td class="pcell"><ProgressBar :value="p.progress_rate" /></td>
            <td><StatusBadge :code="p.plan_status" /></td>
            <td>{{ dash(p.manager_nm) }}</td>
          </tr>
          <tr v-if="loaded && !targets.length"><td colspan="6" class="empty">대상 공정이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>

    <HoverCard v-if="preview.pv.key" :pos="preview.pv.pos" :width="360" :height="270"
      @enter="preview.keep" @leave="preview.leave">
      <p v-if="preview.pv.error">{{ preview.pv.error }}</p>
      <p v-else-if="!preview.pv.data" class="muted">공정 실적을 불러오는 중…</p>
      <template v-else>
        <div class="preview-heading">
          <strong>{{ preview.pv.data.plan.label }}</strong>
          <StatusBadge :code="preview.pv.data.plan.plan_status" />
        </div>
        <p>누적 진척률 {{ preview.pv.data.plan.progress_rate }}%</p>
        <p v-if="!preview.pv.data.history.length" class="muted">등록된 실적 이력이 없습니다.</p>
        <template v-else>
          <strong>최근 실적</strong>
          <table class="t preview-history">
            <thead><tr><th>작업일</th><th>진척률</th><th>공수</th><th>인원</th></tr></thead>
            <tbody>
              <tr v-for="entry in preview.pv.data.history.slice(0, 3)" :key="entry.progress_id">
                <td>{{ entry.work_dt }}</td><td>{{ entry.progress_rate }}%</td>
                <td>{{ dash(entry.man_hour) }}</td><td>{{ dash(entry.worker_cnt) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <p class="muted">클릭하면 전체 실적 이력을 볼 수 있습니다.</p>
      </template>
    </HoverCard>
    <div class="card detail">
      <p v-if="!selectedId" class="muted">위 목록에서 공정을 선택하세요.</p>
      <template v-else-if="plan">
        <h3><span>{{ plan.label }}</span><StatusBadge :code="plan.plan_status" /></h3>
        <form v-if="canWrite" class="fg c6" @submit.prevent="save">
          <label class="f"><span>작업일</span><input v-model="form.work_dt" name="work_dt" type="date" :max="today" /></label>
          <label class="f"><span>누적 진척률(%)</span><input v-model="form.progress_rate" name="progress_rate" type="number" min="0" max="100" step="1" /></label>
          <label class="f"><span>투입 공수(MH)</span><input v-model="form.man_hour" name="man_hour" type="number" step="0.5" /></label>
          <label class="f"><span>투입 인원</span><input v-model="form.worker_cnt" name="worker_cnt" type="number" step="1" /></label>
          <label class="f"><span>작업자</span>
            <select v-model="form.worker_emp_no" name="worker_emp_no">
              <option value="">-</option>
              <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ userLabel(u) }}</option>
            </select>
          </label>
          <div><button class="btn pri" type="submit">실적 저장</button></div>
          <label class="f"><span>비고</span><input v-model="form.remark" name="remark" /></label>
        </form>
        <h4>실적 이력</h4>
        <div class="tw">
          <table class="t">
            <thead><tr><th>작업일</th><th>누적 진척률</th><th class="num">공수</th><th class="num">인원</th><th>작업자</th><th>비고</th><th v-if="canWrite"></th></tr></thead>
            <tbody>
              <tr v-for="h in history" :key="h.progress_id">
                <td>{{ h.work_dt }}</td>
                <td>{{ Number(h.progress_rate) }}%</td>
                <td class="num">{{ dash(h.man_hour) }}</td>
                <td class="num">{{ dash(h.worker_cnt) }}</td>
                <td>{{ dash(h.worker_nm) }}</td>
                <td class="wrap">{{ h.remark || '' }}</td>
                <td v-if="canWrite" class="del"><button class="btn sm danger" type="button" @click="remove(h)">삭제</button></td>
              </tr>
              <tr v-if="!history.length"><td :colspan="canWrite ? 7 : 6" class="empty">실적 이력이 없습니다.</td></tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import { fail, session, toast, userLabel } from '../stores/session.js'
import { blankNull, dash, numOrNull } from '../utils/date.js'
import PageHead from '../components/PageHead.vue'
import ProgressBar from '../components/ProgressBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import HoverCard from '../components/HoverCard.vue'
import { useHoverPreview } from '../utils/hoverPreview.js'

defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const getProgress = (planId) => api.get(`/api/plans/${planId}/progress`)
const preview = useHoverPreview(getProgress)
const hulls = ref([])
const users = ref([])
const hullNo = ref('')
const includeDone = ref(false)
const targets = ref([])
const today = ref('')
const loaded = ref(false)
const selectedId = ref(null)
const plan = ref(null)
const history = ref([])
const form = reactive({ work_dt: '', progress_rate: '', man_hour: '', worker_cnt: '', worker_emp_no: '', remark: '' })

function resetForm() {
  Object.assign(form, {
    work_dt: today.value, progress_rate: plan.value ? Number(plan.value.progress_rate) : '', man_hour: '', worker_cnt: '',
    worker_emp_no: session.me?.emp_no || '', remark: '',
  })
}

async function loadTargets() {
  preview.close()
  preview.clear()
  if (!hullNo.value) return
  try {
    const r = await api.get(`/api/hulls/${hullNo.value}/progress-targets`, { include_done: includeDone.value })
    targets.value = r.plans
    today.value = r.today
    loaded.value = true
  } catch (e) { fail(e) }
}

function changeHull() {
  selectedId.value = null
  plan.value = null
  history.value = []
  loadTargets()
}

function apply(r) {
  plan.value = r.plan
  history.value = r.history
}

async function select(p) {
  preview.close()
  selectedId.value = p.plan_id
  try {
    apply(await getProgress(p.plan_id))
    resetForm()
  } catch (e) { fail(e) }
}

async function save() {
  const rate = numOrNull(form.progress_rate)
  try {
    const r = await api.put(`/api/plans/${selectedId.value}/progress/${form.work_dt || '-'}`, {
      progress_rate: rate, man_hour: numOrNull(form.man_hour), worker_cnt: numOrNull(form.worker_cnt),
      worker_emp_no: blankNull(form.worker_emp_no), remark: blankNull(form.remark.trim()),
    })
    apply(r)
    toast(rate >= 100 ? '실적 저장 — 공정이 완료 처리되었습니다.' : '실적이 저장되었습니다.', 'success')
    resetForm()
    await loadTargets()
  } catch (e) { fail(e) }
}

async function remove(h) {
  if (!confirm('실적을 삭제합니다.')) return
  try {
    apply(await api.del(`/api/progress/${h.progress_id}`))
    toast('실적이 삭제되었습니다.', 'success')
    resetForm()
    await loadTargets()
  } catch (e) { fail(e) }
}

onMounted(async () => {
  try {
    const [h, u] = await Promise.all([api.get('/api/progress-hulls'), api.get('/api/users/options')])
    hulls.value = h.hulls
    users.value = u
    hullNo.value = h.default_hull_no || h.hulls[0]?.hull_no || ''
  } catch (e) { return fail(e) }
  loadTargets()
})
</script>

<style scoped>
.preview-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.preview-history { margin-top: 6px; }
.hsel { width: 166px; }
.pcell { width: 250px; }
.detail { margin-top: 12px; }
.detail > p { margin: 4px 0; }
.detail h4 { font-size: 13.5px; margin: 18px 0 8px; }
.del { text-align: center; }
</style>
