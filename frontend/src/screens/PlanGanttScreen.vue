<template>
  <div class="pg">
    <PageHead title="공정 계획" desc="막대 또는 좌측 공정명을 클릭하면 아래에 상세·수정 패널이 열립니다." :readonly="!canWrite" />
    <div class="toolbar">
      <select v-model="hullNo" class="hsel" aria-label="호선" @change="selectHull(hullNo)">
        <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
      <select v-model="blockId" class="bsel" aria-label="블록" @change="closePanel">
        <option value="">블록 전체</option>
        <option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option>
      </select>
      <select v-model.number="scale" class="ssel" aria-label="배율">
        <option v-for="s in SCALES" :key="s.v" :value="s.v">{{ s.l }}</option>
      </select>
      <span>호선 진척</span>
      <div class="hp"><ProgressBar :value="data.hull_progress ?? 0" /></div>
      <div class="grow"></div>
      <button v-if="canWrite" class="btn pri" type="button" @click="newPlan">+ 공정 추가</button>
    </div>
    <div class="legend">
      <span v-for="c in codeList('PLANSTAT')" :key="c.code"><i :style="{ background: `var(--c-${c.code})` }"></i>{{ c.name }}</span>
      <span>📐 도면 대기</span>
      <span class="muted">— 선후행 연결선 / 빨간선 = 오늘({{ data.today }})</span>
    </div>

    <div ref="scroller" class="gwrap">
      <div v-if="loaded && !visible.length" class="gempty">표시할 공정이 없습니다.</div>
      <div v-else class="ginner" :style="{ width: L.width + 'px' }">
        <div class="ghead">
          <div class="gcorner">블록 / 공정</div>
          <div class="gmonths" :style="{ width: L.timeline + 'px' }">
            <div v-for="m in L.months" :key="m.label" class="gm" :style="{ left: m.x + 'px' }">{{ m.label }}</div>
          </div>
        </div>
        <div class="gbody" :style="{ height: visible.length * ROW + 'px' }">
          <div class="glayer" :style="{ width: L.timeline + 'px' }">
            <div v-if="selIdx >= 0" class="gsel" :style="{ top: selIdx * ROW + 'px' }"></div>
            <div v-for="m in L.months" :key="m.label" class="gml" :style="{ left: m.x + 'px' }"></div>
            <svg class="gdeps" :width="L.timeline" :height="visible.length * ROW">
              <path v-for="(d, i) in deps" :key="i" :d="d" />
            </svg>
            <div class="gtoday" :style="{ left: L.todayX + 'px' }"><span>오늘</span></div>
          </div>
          <div v-for="b in L.bars" :key="b.plan.plan_id" class="grow" :class="{ on: b.plan.plan_id === selectedId }">
            <div class="glabel" @click="openPlan(b.plan)">
              <span class="muted bc">{{ b.plan.block_cd || '호선' }}</span>{{ b.plan.proc_nm }}<span v-if="b.plan.drawing_wait" class="dw">📐</span>
            </div>
            <div class="gtrack" :style="{ width: L.timeline + 'px' }">
              <div class="gbar" :style="{ left: b.left + 'px', width: b.width + 'px', '--c': `var(--c-${b.plan.plan_status})` }"
                :title="barTitle(b.plan)" @click="openPlan(b.plan)">
                <i :style="{ width: (b.plan.progress_rate || 0) + '%' }"></i>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="mode" class="card panel">
      <h3 class="phd">
        <span>
          <b>{{ mode === 'new' ? '공정 추가' : current?.label }}</b>
          <template v-if="mode === 'edit' && current">
            <StatusBadge :code="current.plan_status" />
            <span class="pmeta">진척 {{ fmtNum(current.progress_rate) }}% · 실제 {{ dash(current.actual_start_dt) }} ~ {{ dash(current.actual_end_dt) }}</span>
          </template>
        </span>
      </h3>
      <div class="pbody">
        <form class="fg pf" @submit.prevent="save">
          <label class="f s2"><span>블록</span>
            <select v-model="form.block_id" name="block_id">
              <option value="">호선 전체(블록 없음)</option>
              <option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option>
            </select>
          </label>
          <label class="f w2"><span>공정</span>
            <select v-model="form.proc_cd" name="proc_cd"><option v-for="p in procs" :key="p.proc_cd" :value="p.proc_cd">{{ p.proc_nm }}</option></select>
          </label>
          <label class="f"><span>계획 시작</span><input v-model="form.plan_start_dt" name="plan_start_dt" type="date" /></label>
          <label class="f"><span>계획 종료</span><input v-model="form.plan_end_dt" name="plan_end_dt" type="date" /></label>
          <label class="f w2"><span>담당자</span>
            <select v-model="form.manager_emp_no" name="manager_emp_no">
              <option value="">미지정</option>
              <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ userLabel(u) }}</option>
            </select>
          </label>
          <label class="f w3"><span>선행 공정 (Ctrl 다중선택)</span>
            <select v-model="form.pred_plan_ids" name="pred_plan_ids" multiple class="h66">
              <option v-for="p in predOptions" :key="p.plan_id" :value="p.plan_id">{{ p.label }}</option>
            </select>
          </label>
          <label class="f w3"><span>비고</span><textarea v-model="form.remark" name="remark" class="h66"></textarea></label>
          <div class="sall prow">
            <button class="btn pri" type="submit" :disabled="!canWrite">저장</button>
            <button v-if="mode === 'edit'" class="btn danger" type="button" :disabled="!canWrite" @click="remove">삭제</button>
            <button class="btn" type="button" @click="closePanel">닫기</button>
          </div>
        </form>
        <div class="links">
          <p v-if="mode === 'new'" class="muted">저장한 뒤 이 공정에 도면을 연계할 수 있습니다.</p>
          <template v-else>
            <div v-if="links.blockers.length" class="note warn">
              📐 도면 대기: 필수 도면 <b>{{ links.blockers.map((b) => `${b.drawing_no}(${codeName('DWGSTAT', b.dwg_status)})`).join(', ') }}</b> 미배포 → 착수 불가
            </div>
            <div class="ltitle"><b>연계 도면</b> (필수 도면은 배포 전 착수 불가)</div>
            <div class="tw r3">
              <table class="t">
                <thead><tr><th>도면번호</th><th>상태</th><th>필수</th><th></th></tr></thead>
                <tbody>
                  <tr v-for="d in links.links" :key="d.drawing_id">
                    <td><a class="lnk" href="#" @click.prevent="openDrawing(d)">{{ d.drawing_no }}</a></td>
                    <td><StatusBadge group="DWGSTAT" :code="d.dwg_status" /> <span v-if="!d.has_issued" class="b b-warn">미배포</span></td>
                    <td>{{ d.required ? '필수' : '참고' }}</td>
                    <td><button v-if="canWrite" class="btn sm danger" type="button" @click="unlink(d)">해제</button></td>
                  </tr>
                  <tr v-if="!links.links.length"><td colspan="4" class="empty">연계된 도면이 없습니다.</td></tr>
                </tbody>
              </table>
            </div>
            <div v-if="canWrite" class="lrow">
              <select v-model="linkSel" aria-label="도면 선택">
                <option value="">도면 선택</option>
                <option v-for="d in links.available" :key="d.drawing_id" :value="d.drawing_id">{{ d.drawing_no }} {{ d.drawing_nm }}</option>
              </select>
              <label class="chk"><input v-model="linkReq" type="checkbox" />필수</label>
              <button class="btn" type="button" @click="link">+ 연계</button>
            </div>
          </template>
        </div>
      </div>
    </div>
    <DrawingDetail v-if="dwgId" :key="dwgId" :drawing-id="dwgId" :can-write="!!menuByToken('dwg-list')?.can_write"
      @close="dwgId = null" @changed="refreshAfterChange(selectedId)" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import { codeList, codeName, fail, menuByToken, toast, userLabel } from '../stores/session.js'
import DrawingDetail from './DrawingDetail.vue'
import { addDays, blankNull, dash, numOrNull } from '../utils/date.js'
import { depPaths, ganttLayout, LEFT, ROW, SCALES } from '../utils/gantt.js'
import PageHead from '../components/PageHead.vue'
import ProgressBar from '../components/ProgressBar.vue'
import StatusBadge from '../components/StatusBadge.vue'

const props = defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const hulls = ref([])
const procs = ref([])
const users = ref([])
const blocks = ref([])
const hullNo = ref('')
const blockId = ref('')
const scale = ref(4)
const data = ref({ hull_progress: null, today: '', plans: [], deps: [] })
const loaded = ref(false)
const scroller = ref(null)
const selectedId = ref(null)
const mode = ref(null)
const blankForm = () => ({ block_id: '', proc_cd: 'CUT', plan_start_dt: '', plan_end_dt: '', manager_emp_no: '', remark: '', pred_plan_ids: [] })
const form = reactive(blankForm())
const links = reactive({ blockers: [], links: [], available: [] })
const linkSel = ref('')
const linkReq = ref(true)

const fmtNum = (v) => Number(v || 0)
const visible = computed(() => (blockId.value === '' ? data.value.plans : data.value.plans.filter((p) => p.block_id === blockId.value)))
const L = computed(() => ganttLayout(visible.value, data.value.today || '2000-01-01', scale.value))
const deps = computed(() => depPaths(data.value.deps, visible.value, L.value, scale.value))
const selIdx = computed(() => visible.value.findIndex((p) => p.plan_id === selectedId.value))
const current = computed(() => data.value.plans.find((p) => p.plan_id === selectedId.value) || null)
const predOptions = computed(() => data.value.plans.filter((p) => p.plan_id !== selectedId.value))

function barTitle(p) {
  return `${p.label}\n${p.plan_start_dt} ~ ${p.plan_end_dt}\n진척 ${fmtNum(p.progress_rate)}% · ${codeName('PLANSTAT', p.plan_status)}${p.drawing_wait ? '\n📐 도면 대기' : ''}`
}

async function loadPlans(resetScroll = false) {
  const no = hullNo.value
  const keep = scroller.value?.scrollLeft ?? 0
  try {
    const d = await api.get(`/api/hulls/${no}/plans`)
    if (no !== hullNo.value) return
    data.value = d
    loaded.value = true
  } catch (e) { fail(e); return }
  await nextTick()
  const el = scroller.value
  if (!el) return
  el.scrollLeft = resetScroll ? Math.max(0, LEFT + L.value.todayX - el.clientWidth * 0.4) : keep
}

async function loadBlocks() {
  const no = hullNo.value
  try {
    blocks.value = await api.get(`/api/hulls/${no}/blocks`)
  } catch (e) {
    if (e.status !== 403) return fail(e)
    // 호선 메뉴 권한이 없으면 공정에 쓰인 블록으로 대신한다.
    const seen = new Map()
    for (const p of data.value.plans) if (p.block_id && !seen.has(p.block_id)) seen.set(p.block_id, { block_id: p.block_id, block_cd: p.block_cd, block_nm: p.block_nm })
    blocks.value = [...seen.values()]
  }
}

async function selectHull(no) {
  hullNo.value = no
  blockId.value = ''
  closePanel()
  loaded.value = false
  if (!no) return
  await loadPlans(true)
  await loadBlocks()
}

function applyParam() {
  const p = props.param != null ? String(props.param) : ''
  const target = hulls.value.find((h) => h.hull_no === p) || hulls.value.find((h) => h.plan_count > 0) || hulls.value[0]
  selectHull(target?.hull_no || '')
}

function closePanel() {
  mode.value = null
  selectedId.value = null
}

async function loadLinks(id) {
  try {
    Object.assign(links, await api.get(`/api/plans/${id}/drawings`))
  } catch (e) { fail(e) }
}

function openPlan(p) {
  selectedId.value = p.plan_id
  mode.value = 'edit'
  Object.assign(form, {
    block_id: p.block_id ?? '', proc_cd: p.proc_cd, plan_start_dt: p.plan_start_dt, plan_end_dt: p.plan_end_dt,
    manager_emp_no: p.manager_emp_no ?? '', remark: p.remark ?? '', pred_plan_ids: [...(p.pred_plan_ids || [])],
  })
  linkSel.value = ''
  linkReq.value = true
  Object.assign(links, { blockers: [], links: [], available: [] })
  loadLinks(p.plan_id)
}

function newPlan() {
  selectedId.value = null
  mode.value = 'new'
  const today = data.value.today
  Object.assign(form, blankForm(), { block_id: blockId.value, plan_start_dt: today, plan_end_dt: addDays(today, 13) })
}

async function refreshAfterChange(id) {
  await loadPlans(false)
  const p = data.value.plans.find((x) => x.plan_id === id)
  if (p) openPlan(p)
  else closePanel()
}

async function save() {
  const body = {
    block_id: numOrNull(form.block_id), proc_cd: form.proc_cd,
    plan_start_dt: blankNull(form.plan_start_dt), plan_end_dt: blankNull(form.plan_end_dt),
    manager_emp_no: blankNull(form.manager_emp_no), remark: blankNull(form.remark?.trim()),
    pred_plan_ids: form.pred_plan_ids.map(Number),
  }
  const send = (confirmLate) => {
    const b = { ...body, confirm_late_preds: confirmLate }
    return mode.value === 'new' ? api.post(`/api/hulls/${hullNo.value}/plans`, b) : api.patch(`/api/plans/${selectedId.value}`, b)
  }
  let res
  try {
    res = await send(false)
  } catch (e) {
    if (e.code !== 'PRED_LATE_CONFIRM_REQUIRED') return fail(e)
    if (!confirm(e.message)) return
    try { res = await send(true) } catch (e2) { return fail(e2) }
  }
  toast('저장되었습니다.', 'success')
  await refreshAfterChange(res?.plan_id ?? selectedId.value)
}

async function remove() {
  if (!confirm('공정을 삭제합니다. (실적·선후행·도면 연계 함께 삭제)')) return
  try {
    await api.del(`/api/plans/${selectedId.value}`)
    toast('삭제되었습니다.', 'success')
    closePanel()
    await loadPlans(false)
  } catch (e) { fail(e) }
}

async function link() {
  if (!linkSel.value) return toast('도면을 선택하세요.', 'error')
  try {
    await api.post(`/api/plans/${selectedId.value}/drawings`, { drawing_id: Number(linkSel.value), required: linkReq.value })
    toast('도면이 연계되었습니다.', 'success')
    await refreshAfterChange(selectedId.value)
  } catch (e) { fail(e) }
}

async function unlink(d) {
  try {
    await api.del(`/api/plans/${selectedId.value}/drawings/${d.drawing_id}`)
    toast('연계가 해제되었습니다.', 'success')
    await refreshAfterChange(selectedId.value)
  } catch (e) { fail(e) }
}

const dwgId = ref(null)
function openDrawing(d) { dwgId.value = d.drawing_id }

watch(() => props.ctx, applyParam)

onMounted(async () => {
  try {
    const [h, p, u] = await Promise.all([api.get('/api/plan-hulls'), api.get('/api/procs'), api.get('/api/users/options')])
    hulls.value = h
    procs.value = p
    users.value = u
  } catch (e) { return fail(e) }
  applyParam()
})
</script>

<style scoped>
.pg { height: 100%; display: flex; flex-direction: column; }
.toolbar { margin-bottom: 8px; }
.hsel { width: 166px; }
.bsel { width: 128px; }
.ssel { width: 110px; }
.hp { width: 170px; }
.legend { display: flex; gap: 14px; align-items: center; font-size: 12px; margin-bottom: 8px; }
.legend i { display: inline-block; width: 12px; height: 10px; border-radius: 2px; margin-right: 4px; }
.gwrap { flex: 1; min-height: 140px; overflow: auto; background: #fff; border: 1px solid var(--line); border-radius: 6px; position: relative; }
.gempty { padding: 30px; text-align: center; color: var(--muted); }
.ginner { position: relative; }
.ghead { position: sticky; top: 0; z-index: 4; display: flex; height: 34px; background: var(--head); border-bottom: 1px solid var(--line); }
.gcorner { position: sticky; left: 0; z-index: 5; width: 230px; flex: none; background: var(--head); font-weight: 600; padding: 0 9px; line-height: 34px; border-right: 1px solid var(--line); }
.gmonths { position: relative; flex: none; }
.gm { position: absolute; top: 0; bottom: 0; padding: 3px 6px; font-size: 11px; color: var(--muted); border-left: 1px solid var(--line); white-space: nowrap; }
.gbody { position: relative; }
.glayer { position: absolute; left: 230px; top: 0; bottom: 0; pointer-events: none; z-index: 0; }
.gsel { position: absolute; left: 0; right: 0; height: 28px; background: var(--sel); }
.gml { position: absolute; top: 0; bottom: 0; border-left: 1px dashed var(--line); }
.gdeps { position: absolute; left: 0; top: 0; overflow: visible; }
.gdeps path { fill: none; stroke: #64748b; stroke-width: 1; opacity: .55; }
.gtoday { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--err); }
.gtoday span { position: absolute; left: 5px; top: 1px; font-size: 10px; color: var(--err); white-space: nowrap; }
.grow { position: relative; z-index: 1; display: flex; height: 28px; border-bottom: 1px solid var(--line2); }
.glabel { position: sticky; left: 0; z-index: 2; width: 230px; flex: none; background: #fff; padding: 0 9px; line-height: 27px; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-right: 1px solid var(--line); }
.grow.on .glabel { background: var(--sel); }
.glabel:hover { background: var(--hover); }
.bc { display: inline-block; min-width: 33px; }
.dw { margin-left: 4px; }
.gtrack { position: relative; flex: none; }
.gbar { position: absolute; top: 6px; height: 16px; border-radius: 3px; background: color-mix(in srgb, var(--c) 35%, white); overflow: hidden; cursor: pointer; }
.gbar i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--c); }
.panel { flex: none; margin: 10px 0 0; }
.phd { justify-content: flex-start; }
.phd > span { display: flex; align-items: center; gap: 8px; }
.pmeta { font-weight: 400; color: var(--muted); font-size: 13px; }
.pbody { display: grid; grid-template-columns: 1fr 430px; gap: 16px; }
.pf { grid-template-columns: repeat(6, minmax(0, 1fr)); align-content: start; }
.w3 { grid-column: span 3; }
.h66 { height: 66px !important; }
.prow { display: flex; gap: 8px; }
.links { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.links > p { margin: 22px 0 0; }
.ltitle { font-size: 12.5px; }
.lrow { display: flex; gap: 8px; align-items: center; }
.lrow select { flex: 1; }
@media (max-width: 1560px) {
  .pf { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .w2, .w3 { grid-column: span 2; }
}
</style>
