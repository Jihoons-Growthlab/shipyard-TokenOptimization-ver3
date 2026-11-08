<template>
  <div class="dash">
    <PageHead title="대시보드" :desc="`기준일 ${s?.today || session.me?.today || ''} · 호선/공정/도면 현황`" />
    <template v-if="s">
      <div class="kpis">
        <div v-for="k in kpis" :key="k.key" class="card kpi" @click="go(k.link, k.screen)">
          <span>{{ k.label }}</span><b :class="k.cls">{{ k.value }}</b>
        </div>
      </div>
      <div class="grid3">
        <section class="card">
          <h3>호선별 진척률</h3>
          <div v-for="h in s.hull_progress" :key="h.hull_no" class="hp" @click="go(h.link, 'plan-gantt', h.hull_no)">
            <span class="ell" :title="`${h.hull_no} ${h.hull_nm}`">{{ h.hull_no }} {{ h.hull_nm }}</span>
            <div class="hbar"><i :style="{ width: pct(h.progress) + '%' }"></i></div>
            <b>{{ pct(h.progress) }}%</b>
          </div>
        </section>
        <section class="card">
          <h3>공정 상태 분포</h3>
          <div class="donut">
            <svg width="120" height="120" viewBox="0 0 120 120" aria-label="공정 상태 분포">
              <circle cx="60" cy="60" r="40" fill="none" stroke="#e5e7eb" stroke-width="22" />
              <circle v-for="g in donut" :key="g.status" cx="60" cy="60" r="40" fill="none" stroke-width="22"
                :stroke="PLAN_COLOR[g.status]" :stroke-dasharray="`${g.len} ${CIRC - g.len}`" :stroke-dashoffset="-g.off"
                transform="rotate(-90 60 60)" />
              <text x="60" y="62" text-anchor="middle" class="dt">{{ planTotal }}</text>
              <text x="60" y="80" text-anchor="middle" class="ds">전체</text>
            </svg>
            <ul class="legend">
              <li v-for="g in s.plan_status" :key="g.status"><i :style="{ background: PLAN_COLOR[g.status] }"></i>{{ codeName('PLANSTAT', g.status) }} <b>{{ g.count }}</b></li>
            </ul>
          </div>
        </section>
        <section class="card">
          <h3>분야별 도면 상태</h3>
          <div v-for="d in s.drawing_disciplines" :key="d.discipline" class="disc">
            <div>{{ d.name }} <span class="muted">({{ d.total }})</span></div>
            <div class="stack">
              <i v-for="st in DWG_ORDER.filter((x) => d.counts[x])" :key="st" :style="{ flex: d.counts[st], background: DWG_COLOR[st] }"
                :title="`${codeName('DWGSTAT', st)} ${d.counts[st]}`"></i>
            </div>
          </div>
          <ul class="legend row">
            <li v-for="st in DWG_ORDER" :key="st"><i :style="{ background: DWG_COLOR[st] }"></i>{{ codeName('DWGSTAT', st) }}</li>
          </ul>
        </section>

        <section class="card">
          <h3>월별 인도 예정</h3>
          <div class="months">
            <div v-for="m in s.deliveries" :key="m.month" class="mon">
              <span class="mv">{{ m.count }}</span>
              <i :style="{ height: Math.round((m.count / maxDelivery) * 80) + 'px' }"></i>
              <span class="ml">{{ m.month.slice(2) }}</span>
              <span class="mh">{{ m.hull_nos.join(',') }}</span>
            </div>
          </div>
        </section>
        <section class="card">
          <h3>지연 공정 <span class="b b-bad">{{ s.delay_list.count }}</span></h3>
          <div v-for="p in s.delay_list.items" :key="p.plan_id" class="li" @click="go(p.link, 'plan-gantt', p.hull_no)">
            <span>{{ p.hull_no }} {{ p.label }}</span><span class="muted">{{ pct(p.progress_rate) }}% · 계획종료 {{ p.plan_end_dt }}</span>
          </div>
          <p v-if="!s.delay_list.items.length" class="none">지연 공정이 없습니다.</p>
        </section>
        <section class="card">
          <h3>도면 대기 공정 <span class="b b-warn">{{ s.waiting_list.count }}</span></h3>
          <div v-for="p in s.waiting_list.items" :key="p.plan_id" class="li" @click="go(p.link, 'plan-gantt', p.hull_no)">
            <span>{{ p.hull_no }} {{ p.label }}</span><span class="muted">착수 {{ p.plan_start_dt }} · {{ p.blockers.join(', ') }}</span>
          </div>
          <p v-if="!s.waiting_list.items.length" class="none">대기 중인 공정이 없습니다.</p>
        </section>
      </div>
      <section class="card">
        <h3>도면 개정 영향 공정 <span class="b b-info">{{ s.impact_list.count }}</span></h3>
        <div v-for="i in s.impact_list.items" :key="`${i.drawing_id}-${i.plan_id}`" class="li" @click="dwgId = i.drawing_id">
          <span>{{ i.drawing_no }} Rev{{ i.rev_no }} → {{ i.plan_label }} <StatusBadge :code="i.plan_status" /></span>
          <span class="muted">{{ i.change_desc }} · 배포 {{ i.issue_dt }}</span>
        </div>
        <p v-if="!s.impact_list.items.length" class="none">최근 개정된 도면의 영향 공정이 없습니다.</p>
      </section>
    </template>
    <DrawingDetail v-if="dwgId" :key="dwgId" :drawing-id="dwgId" :can-write="!!menuByToken('dwg-list')?.can_write" @close="dwgId = null" @changed="load" />
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref } from 'vue'
import { api } from '../api/client.js'
import { codeName, fail, menuByToken, session } from '../stores/session.js'
import PageHead from '../components/PageHead.vue'
import StatusBadge from '../components/StatusBadge.vue'
import DrawingDetail from './DrawingDetail.vue'

defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })
const navigate = inject('navigate', () => {})

const PLAN_COLOR = { PLAN: '#94a3b8', READY: '#0ea5e9', WORK: '#2563eb', DONE: '#16a34a', DELAY: '#dc2626' }
const DWG_ORDER = ['ISSUED', 'APPROVED', 'REVIEW', 'DRAFT']
const DWG_COLOR = { ISSUED: '#16a34a', APPROVED: '#0ea5e9', REVIEW: '#f59e0b', DRAFT: '#94a3b8' }
const CIRC = 2 * Math.PI * 40

const s = ref(null)
const dwgId = ref(null)

const pct = (v) => Math.round(Number(v) || 0)
const kpis = computed(() => {
  const k = s.value.kpi
  return [
    { key: 'active_hulls', label: '진행 호선', screen: 'hull-list', cls: '' },
    { key: 'delay_plans', label: '지연 공정', screen: 'plan-gantt', cls: k.delay_plans.value ? 'err' : '' },
    { key: 'waiting_plans', label: '도면 대기 공정', screen: 'plan-gantt', cls: k.waiting_plans.value ? 'warn' : '' },
    { key: 'pending_drawings', label: '결재·배포 대기 도면', screen: 'dwg-approval', cls: k.pending_drawings.value ? 'warn' : '' },
  ].map((x) => ({ ...x, value: k[x.key].value, link: k[x.key].link }))
})
const planTotal = computed(() => s.value.plan_status.reduce((a, g) => a + g.count, 0))
const donut = computed(() => {
  let off = 0
  return s.value.plan_status.filter((g) => g.count).map((g) => {
    const len = planTotal.value ? (g.count / planTotal.value) * CIRC : 0
    const seg = { status: g.status, len, off }
    off += len
    return seg
  })
})
const maxDelivery = computed(() => Math.max(1, ...s.value.deliveries.map((m) => m.count)))

/** 서버 link 우선, 없으면 명세의 기본 이동 대상. */
function go(link, screen, param = null) {
  navigate(link?.screen || screen, link ? (link.param ?? null) : param)
}
async function load() {
  try { s.value = await api.get('/api/dashboard/summary') } catch (e) { fail(e) }
}
onMounted(load)
</script>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.kpi { margin: 0; cursor: pointer; display: flex; flex-direction: column; gap: 2px; }
.kpi:hover { border-color: var(--pri); }
.kpi span { font-size: 12px; color: var(--muted); }
.kpi b { font-size: 26px; font-weight: 700; line-height: 1.2; }
.kpi b.err { color: var(--err); }
.kpi b.warn { color: var(--warn); }
.grid3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.grid3 .card { margin: 0; min-width: 0; }
.hp { display: grid; grid-template-columns: 130px 1fr 44px; gap: 8px; align-items: center; padding: 3px 0; cursor: pointer; }
.hp:hover { background: var(--hover); }
.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hbar { height: 14px; border-radius: 7px; background: #e5e7eb; overflow: hidden; }
.hbar i { display: block; height: 100%; background: var(--pri); }
.donut { display: flex; align-items: center; gap: 24px; }
.dt { font-size: 20px; font-weight: 700; fill: var(--ink); }
.ds { font-size: 10px; fill: var(--muted); }
.legend { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: 12px; }
.legend.row { flex-direction: row; gap: 12px; margin-top: 10px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.disc { margin-bottom: 8px; font-size: 12px; }
.stack { display: flex; height: 16px; border-radius: 3px; overflow: hidden; background: #e5e7eb; margin-top: 4px; }
.stack i { display: block; }
.months { height: 130px; display: flex; align-items: flex-end; justify-content: space-around; gap: 8px; }
.mon { display: flex; flex-direction: column; align-items: center; gap: 3px; font-size: 10.5px; }
.mon i { display: block; width: 44px; background: var(--navy2); }
.mv { font-size: 11px; font-weight: 600; }
.ml { color: var(--muted); }
.li { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 7px 4px; border-bottom: 1px solid var(--line2); cursor: pointer; }
.li:last-of-type { border-bottom: 0; }
.li:hover { background: var(--hover); }
.li .muted { font-size: 12px; white-space: nowrap; }
.none { color: var(--muted); text-align: center; margin: 18px 0; }
@media (max-width: 1100px) {
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .grid3 { grid-template-columns: 1fr; }
}
</style>
