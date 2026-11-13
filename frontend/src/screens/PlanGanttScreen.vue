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
      <span><i class="lg sat"></i>토요일</span>
      <span><i class="lg sun"></i>일요일·공휴일</span>
      <span class="muted">— 선후행 연결선 / 빨간선 = 오늘({{ data.today }})</span>
    </div>

    <div ref="scroller" class="gwrap">
      <div v-if="loaded && !visible.length" class="gempty">표시할 공정이 없습니다.</div>
      <div v-else class="ginner" :style="{ width: L.width + 'px' }">
        <div class="ghead">
          <div class="gcorner">블록 / 공정</div>
          <div class="gmonths" :style="{ width: L.timeline + 'px' }">
            <i v-for="o in holidays" :key="o.date" class="ghol" :style="{ left: o.x + 'px', width: Math.max(scale, 3) + 'px' }" :title="`${o.date} ${o.name}`"></i>
            <div v-for="m in L.months" :key="m.label" class="gm" :style="{ left: m.x + 'px' }">{{ m.label }}</div>
          </div>
        </div>
        <div class="gbody" :style="{ height: visible.length * ROW + 'px' }">
          <div class="glayer" :style="{ width: L.timeline + 'px' }">
            <div v-if="selIdx >= 0" class="gsel" :style="{ top: selIdx * ROW + 'px' }"></div>
            <div v-for="o in offs" :key="o.date" class="goff" :class="o.kind" :style="{ left: o.x + 'px', width: scale + 'px' }"></div>
            <div v-for="m in L.months" :key="m.label" class="gml" :style="{ left: m.x + 'px' }"></div>
            <svg class="gdeps" :width="L.timeline" :height="visible.length * ROW">
              <defs>
                <marker id="gdep-arrow" viewBox="0 0 6 6" refX="5.5" refY="3" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L6 3L0 6z" fill="#64748b" /></marker>
                <marker id="gdep-arrow-hi" viewBox="0 0 6 6" refX="5.5" refY="3" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L6 3L0 6z" fill="#2563eb" /></marker>
              </defs>
              <path v-for="(d, i) in depsOrdered" :key="i" :d="d.d" :class="{ hi: d.hi }" :marker-end="d.hi ? 'url(#gdep-arrow-hi)' : 'url(#gdep-arrow)'" />
            </svg>
            <div class="gtoday" :style="{ left: L.todayX + 'px' }"><span>오늘</span></div>
          </div>
          <div v-for="b in L.bars" :key="b.plan.plan_id" class="grow" :class="{ on: b.plan.plan_id === selectedId, rel: related.has(b.plan.plan_id) }">
            <div class="glabel" @click="openPlan(b.plan)">
              <span class="muted bc">{{ b.plan.block_cd || '호선' }}</span>{{ b.plan.proc_nm }}<span v-if="b.plan.drawing_wait" class="dw">📐</span>
            </div>
            <div class="gtrack" :style="{ width: L.timeline + 'px' }">
              <div class="gbar" :class="{ dragging: drag?.id === b.plan.plan_id, movable: canWrite, sel: b.plan.plan_id === selectedId }"
                :style="{ ...barBox(b), '--c': `var(--c-${b.plan.plan_status})` }"
                :aria-label="barTitle(b.plan)" @click="onBarClick(b.plan)" @pointerdown="startDrag($event, b, 'move')"
                @mouseenter="onBarEnter(b.plan.plan_id, $event)" @mouseleave="onBarLeave">
                <i :style="{ width: (b.plan.progress_rate || 0) + '%' }"></i>
                <template v-if="canWrite">
                  <span class="gh l" @pointerdown.stop="startDrag($event, b, 'start')"></span>
                  <span class="gh r" @pointerdown.stop="startDrag($event, b, 'end')"></span>
                </template>
              </div>
              <span class="gpct" :style="{ left: `calc(${barBox(b).left} + ${barBox(b).width} + 6px)` }">{{ fmtNum(b.plan.progress_rate) }}%</span>
              <div v-if="drag?.id === b.plan.plan_id && drag.moved" class="gtip" :style="{ left: barBox(b).left }">
                {{ dragDates(b.plan).join(' ~ ') }}
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
    <HoverCard v-if="hp.pv.key && !drag && tip" :pos="hp.pv.pos" :width="400" :height="380" @enter="hp.keep" @leave="hp.leave">
      <div class="pv">
        <div class="pvh"><b>{{ tip.p.label }}</b><StatusBadge :code="tip.p.plan_status" /><span v-if="tip.p.drawing_wait">📐</span></div>
        <div class="pvr"><span>계획</span><span>{{ tip.p.plan_start_dt }} ~ {{ tip.p.plan_end_dt }} <span class="muted">({{ tip.days }}일)</span></span></div>
        <div class="pvr"><span>실제</span>{{ dash(tip.p.actual_start_dt) }} ~ {{ dash(tip.p.actual_end_dt) }}</div>
        <div class="pvr"><span>진척</span><ProgressBar :value="tip.p.progress_rate || 0" /></div>
        <div v-if="tip.late > 0" class="pvr"><span>지연</span><b class="err">종료 예정일 {{ tip.late }}일 경과</b></div>
        <div class="pvr"><span>담당자</span>{{ tip.p.manager_nm || '미지정' }}</div>
        <div class="pvr"><span>선행</span>{{ tip.preds.map((x) => x.label).join(', ') || '-' }}</div>
        <div class="pvr"><span>후행</span>{{ tip.succs.map((x) => x.label).join(', ') || '-' }}</div>
        <div v-if="tip.p.remark" class="pvr"><span>비고</span><span class="pre">{{ tip.p.remark }}</span></div>
        <div v-if="tip.p.blockers.length" class="note warn">📐 도면 대기: {{ tip.p.blockers.map((b) => `${b.drawing_no}(${codeName('DWGSTAT', b.dwg_status)})`).join(', ') }} 미배포 → 착수 불가</div>
        <p v-if="hp.pv.error" class="muted">{{ hp.pv.error }}</p>
        <p v-else-if="!hp.pv.data" class="muted">연계 도면 불러오는 중…</p>
        <table v-else-if="hp.pv.data.links.length" class="pvt">
          <thead><tr><th>연계 도면</th><th>상태</th><th>필수</th></tr></thead>
          <tbody>
            <tr v-for="d in hp.pv.data.links" :key="d.drawing_id">
              <td>{{ d.drawing_no }}</td>
              <td><StatusBadge group="DWGSTAT" :code="d.dwg_status" /> <span v-if="!d.has_issued" class="b b-warn">미배포</span></td>
              <td>{{ d.required ? '필수' : '참고' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="muted">연계된 도면이 없습니다.</div>
        <div class="pvf muted">{{ canWrite ? '클릭하면 수정 패널이 열리고, 끌면 일정을 옮깁니다.' : '클릭하면 상세 패널이 열립니다.' }}</div>
      </div>
    </HoverCard>
    <DrawingDetail v-if="dwgId" :key="dwgId" :drawing-id="dwgId" :can-write="!!menuByToken('dwg-list')?.can_write"
      @close="dwgId = null" @changed="refreshAfterChange(selectedId)" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import { codeList, codeName, fail, menuByToken, toast, userLabel } from '../stores/session.js'
import DrawingDetail from './DrawingDetail.vue'
import { addDays, blankNull, dash, diffDays, numOrNull } from '../utils/date.js'
import HoverCard from '../components/HoverCard.vue'
import { useHoverPreview } from '../utils/hoverPreview.js'
import { depPaths, ganttLayout, LEFT, offDays, ROW, SCALES } from '../utils/gantt.js'
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
// 마우스를 올린(없으면 선택한) 공정의 선후행 연결선을 강조하고 맨 위에 그린다.
const hoverId = ref(null)
const focusId = computed(() => hoverId.value ?? selectedId.value)
const depsOrdered = computed(() => {
  const f = focusId.value
  const all = deps.value.map((d) => ({ ...d, hi: f != null && (d.from === f || d.to === f) }))
  return [...all.filter((d) => !d.hi), ...all.filter((d) => d.hi)]
})
const related = computed(() => new Set(depsOrdered.value.filter((d) => d.hi).flatMap((d) => [d.from, d.to])))
function onBarEnter(id, ev) {
  if (drag.value) return
  hoverId.value = id
  hp.enter(id, ev)
}
function onBarLeave() {
  hoverId.value = null
  hp.leave()
}
const offs = computed(() => offDays(L.value, scale.value))
const holidays = computed(() => offs.value.filter((o) => o.kind === 'hol'))
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
    hp.clear()
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

// 간트 드래그: 막대 이동(move), 양 끝 핸들로 시작/종료 조정. 하루 단위로 맞추고, 놓으면 서버가 후행 공정을 연쇄 조정한다.
const drag = ref(null)
let suppressClick = false

function dragDates(p) {
  const d = drag.value
  return [addDays(p.plan_start_dt, d.ds), addDays(p.plan_end_dt, d.de)]
}

function barBox(b) {
  const d = drag.value
  if (!d || d.id !== b.plan.plan_id) return { left: b.left + 'px', width: b.width + 'px' }
  return { left: b.left + d.ds * scale.value + 'px', width: b.width + (d.de - d.ds) * scale.value + 'px' }
}

function startDrag(ev, b, kind) {
  if (!props.canWrite || ev.button !== 0) return
  hp.close()
  ev.preventDefault()
  const days = Math.round(b.width / scale.value) // 기간 일수(시작·종료 포함)
  drag.value = { id: b.plan.plan_id, kind, x0: ev.clientX, ds: 0, de: 0, moved: false, days }
  window.addEventListener('pointermove', onDragMove)
  window.addEventListener('pointerup', endDrag, { once: true })
}

function onDragMove(ev) {
  const d = drag.value
  if (!d) return
  const dx = ev.clientX - d.x0
  if (!d.moved && Math.abs(dx) < 3) return
  d.moved = true
  const n = Math.round(dx / scale.value)
  if (d.kind === 'move') { d.ds = n; d.de = n }
  else if (d.kind === 'start') { d.ds = Math.min(n, d.days - 1); d.de = 0 }
  else { d.ds = 0; d.de = Math.max(n, 1 - d.days) }
}

async function endDrag() {
  window.removeEventListener('pointermove', onDragMove)
  const d = drag.value
  if (!d?.moved) { drag.value = null; return }
  suppressClick = true
  setTimeout(() => { suppressClick = false }, 0)
  const p =data.value.plans.find((x) => x.plan_id === d.id)
  if (!p || (d.ds === 0 && d.de === 0)) { drag.value = null; return }
  const [s, e] = dragDates(p)
  const send = (confirmLate) => api.patch(`/api/plans/${d.id}/schedule`, { plan_start_dt: s, plan_end_dt: e, confirm_late_preds: confirmLate })
  let res
  try {
    res = await send(false)
  } catch (err) {
    if (err.code !== 'PRED_LATE_CONFIRM_REQUIRED' || !confirm(err.message)) {
      if (err.code !== 'PRED_LATE_CONFIRM_REQUIRED') fail(err)
      drag.value = null
      return
    }
    try { res = await send(true) } catch (err2) { drag.value = null; return fail(err2) }
  }
  const n = res.shifted_plan_ids.length
  toast(n ? `저장되었습니다. 후행 공정 ${n}건의 일정이 함께 조정되었습니다.` : '저장되었습니다.', 'success')
  await loadPlans(false)
  drag.value = null
  if (selectedId.value != null) await refreshAfterChange(selectedId.value)
}

function onBarClick(p) {
  if (suppressClick) { suppressClick = false; return }
  openPlan(p)
}

// 막대 마우스오버 상세 카드(명세 외 요청 기능). 공정 정보는 화면 데이터에서, 연계 도면만 불러온다.
const hp = useHoverPreview((id) => api.get(`/api/plans/${id}/drawings`))
const tip = computed(() => {
  const p = data.value.plans.find((x) => x.plan_id === hp.pv.key)
  if (!p) return null
  const byId = new Map(data.value.plans.map((x) => [x.plan_id, x]))
  const today = data.value.today
  return {
    p,
    days: diffDays(p.plan_end_dt, p.plan_start_dt) + 1,
    late: p.plan_status !== 'DONE' && today > p.plan_end_dt ? diffDays(today, p.plan_end_dt) : 0,
    preds: p.pred_plan_ids.map((id) => byId.get(id)).filter(Boolean),
    succs: data.value.plans.filter((x) => x.pred_plan_ids.includes(p.plan_id)),
  }
})

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
.gwrap { flex: 1; min-height: 140px; overflow: auto; background: #fff; border: 1px solid #e2e7ef; border-radius: 10px; position: relative; box-shadow: var(--shadow-sm); }
.gempty { padding: 30px; text-align: center; color: var(--muted); }
.ginner { position: relative; }
.ghead { position: sticky; top: 0; z-index: 4; display: flex; height: 34px; background: var(--head); border-bottom: 1px solid var(--line); }
.gcorner { position: sticky; left: 0; z-index: 5; width: 230px; flex: none; background: var(--head); font-weight: 600; padding: 0 9px; line-height: 34px; border-right: 1px solid var(--line); }
.gmonths { position: relative; flex: none; }
.gm { position: absolute; top: 0; bottom: 0; padding: 4px 7px; font-size: 11px; font-weight: 600; color: #475569; border-left: 1px solid var(--line); white-space: nowrap; }
.gbody { position: relative; }
.glayer { position: absolute; left: 230px; top: 0; bottom: 0; pointer-events: none; z-index: 0; }
.gsel { position: absolute; left: 0; right: 0; height: 28px; background: var(--sel); }
.goff { position: absolute; top: 0; bottom: 0; }
.goff.sat { background: rgba(100, 116, 139, .13); }
.goff.sun, .goff.hol { background: rgba(220, 38, 38, .07); }
.ghol { position: absolute; bottom: 0; height: 6px; background: var(--err); opacity: .75; cursor: help; z-index: 1; }
.lg { display: inline-block; width: 12px; height: 10px; margin-right: 4px; border: 1px solid var(--line); vertical-align: -1px; }
.lg.sat { background: rgba(100, 116, 139, .22); }
.lg.sun { background: rgba(220, 38, 38, .16); }
.gml { position: absolute; top: 0; bottom: 0; border-left: 1px dashed var(--line); }
.gdeps { position: absolute; left: 0; top: 0; overflow: visible; }
.gdeps path { fill: none; stroke: #64748b; stroke-width: 1; opacity: .5; stroke-linejoin: round; transition: stroke var(--t-fast), opacity var(--t-fast); }
.gdeps path.hi { stroke: var(--pri); stroke-width: 1.6; opacity: 1; }
.gtoday { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--err); box-shadow: 0 0 6px rgba(220, 38, 38, .35); }
.gtoday span { position: absolute; left: 4px; top: 2px; font-size: 10px; font-weight: 700; color: #fff; background: var(--err); padding: 0 5px; border-radius: 8px; line-height: 15px; white-space: nowrap; }
.grow { position: relative; z-index: 1; display: flex; height: 28px; border-bottom: 1px solid var(--line2); transition: background var(--t-fast); }
.grow:hover, .grow.rel { background: rgba(37, 99, 235, .035); }
.grow:hover .gpct, .grow.on .gpct, .grow.rel .gpct { opacity: 1; }
.glabel { position: sticky; left: 0; z-index: 2; width: 230px; flex: none; background: #fff; padding: 0 9px; line-height: 27px; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-right: 1px solid var(--line); transition: background var(--t-fast); }
.grow.on .glabel { box-shadow: inset 3px 0 0 var(--pri); }
.grow.on .glabel { background: var(--sel); }
.glabel:hover { background: var(--hover); }
.bc { display: inline-block; min-width: 33px; }
.dw { margin-left: 4px; }
.gtrack { position: relative; flex: none; }
.gbar { position: absolute; top: 6px; height: 16px; border-radius: 5px; background: color-mix(in srgb, var(--c) 28%, white); overflow: hidden; cursor: pointer;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c) 45%, transparent), 0 1px 2px rgba(15, 23, 42, .08);
  transition: left var(--t-med) var(--ease), width var(--t-med) var(--ease), transform var(--t-fast), box-shadow var(--t-fast), filter var(--t-fast); }
.gbar i { position: absolute; left: 0; top: 0; bottom: 0; background: linear-gradient(180deg, color-mix(in srgb, var(--c) 78%, white), var(--c)); pointer-events: none;
  transform-origin: left; animation: grow-x var(--t-slow) var(--ease) both; }
.gbar:hover { transform: translateY(-1px); box-shadow: inset 0 0 0 1px var(--c), 0 4px 10px color-mix(in srgb, var(--c) 30%, transparent); filter: saturate(1.1); }
.gbar.sel { box-shadow: 0 0 0 2px #fff, 0 0 0 4px color-mix(in srgb, var(--c) 70%, transparent); }
.gbar.movable { cursor: grab; touch-action: none; user-select: none; }
.gbar.dragging { cursor: grabbing; z-index: 3; opacity: .92; transition: none; transform: translateY(-2px);
  box-shadow: 0 0 0 2px var(--c), 0 8px 18px color-mix(in srgb, var(--c) 35%, transparent); }
.gpct { position: absolute; top: 7px; font-size: 10px; font-weight: 600; color: var(--muted); opacity: 0; pointer-events: none; white-space: nowrap; transition: opacity var(--t-fast); }
.gh { position: absolute; top: 0; bottom: 0; width: 6px; cursor: ew-resize; z-index: 1; }
.gh.l { left: 0; }
.gh.r { right: 0; }
.gh::after { content: ''; position: absolute; top: 4px; bottom: 4px; left: 2px; width: 2px; border-radius: 1px; background: #fff; opacity: 0; transition: opacity var(--t-fast); }
.gbar:hover .gh { background: color-mix(in srgb, var(--c) 55%, transparent); }
.gbar:hover .gh::after { opacity: .9; }
.pv .err { color: var(--err); }
.pv .pre { white-space: pre-wrap; }
.pv .note { margin: 0; }
.gtip { position: absolute; top: -16px; z-index: 6; font-size: 10.5px; font-weight: 600; white-space: nowrap; background: #1e293b; color: #fff; padding: 2px 7px; border-radius: 6px; pointer-events: none; box-shadow: var(--shadow-md); }
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
