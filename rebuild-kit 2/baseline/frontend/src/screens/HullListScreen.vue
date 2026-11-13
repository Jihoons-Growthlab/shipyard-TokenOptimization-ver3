<template>
  <div>
    <PageHead title="호선 목록" desc="행에 마우스를 올리면 미리보기가 뜨고, 더블클릭하거나 [상세]를 누르면 호선 상세 팝업이 열립니다." :readonly="!canWrite" />
    <form class="toolbar" @submit.prevent="load">
      <select v-model="f.status" class="fsel" aria-label="상태">
        <option value="">상태 전체</option>
        <option v-for="c in codeList('HULLSTAT')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <select v-model="f.ship_type" class="fsel" aria-label="선종">
        <option value="">선종 전체</option>
        <option v-for="c in codeList('SHIPTYPE')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <input v-model.trim="f.q" class="fq" placeholder="호선번호/호선명/선주" />
      <button class="btn pri" type="submit">조회</button>
      <button class="btn" type="button" @click="resetFilter">초기화</button>
      <div class="grow"></div>
      <button v-if="canWrite" class="btn pri" type="button" @click="openDetail(null)">+ 호선 등록</button>
    </form>
    <div class="tw">
      <table class="t hull-table">
        <thead>
          <tr>
            <th>호선번호</th><th>호선명</th><th>선종</th><th>상태</th><th>선주</th><th>선급</th><th>도크</th>
            <th>계약일</th><th>인도예정</th><th>진척률</th><th class="num">지연</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in hulls" :key="h.hull_no" class="click" :class="{ on: selected === h.hull_no }"
            @click="selected = h.hull_no" @dblclick="openDetail(h.hull_no)"
            @mouseenter="hp.enter(h.hull_no, $event)" @mouseleave="hp.leave">
            <td><b>{{ h.hull_no }}</b></td>
            <td>{{ h.hull_nm }}</td>
            <td>{{ codeName('SHIPTYPE', h.ship_type) }}</td>
            <td><span class="b b-info">{{ codeName('HULLSTAT', h.hull_status) }}</span></td>
            <td>{{ h.owner_nm }}</td>
            <td>{{ h.class_society }}</td>
            <td>{{ dash(h.dock_no) }}</td>
            <td>{{ h.contract_dt }}</td>
            <td>{{ h.delivery_dt }}</td>
            <td class="pcell"><ProgressBar v-if="h.progress !== null" :value="h.progress" /><span v-else class="muted">계획 없음</span></td>
            <td class="num">{{ h.delay_count || '-' }}</td>
            <td><button class="btn sm" type="button" @click.stop="openDetail(h.hull_no)">상세</button></td>
          </tr>
          <tr v-if="loaded && !hulls.length"><td colspan="12" class="empty">조회된 호선이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="total">총 {{ hulls.length }}척</div>
    <section v-if="hulls.length" class="yard-section">
      <div class="yard-head">
        <div>
          <h2>3D 조선소</h2>
          <p class="muted">선체에 마우스를 올리면 요약, 클릭하면 상세를 볼 수 있습니다. 배치는 시뮬레이션입니다.</p>
        </div>
        <div v-if="pageCount > 1" class="yard-pages">
          <button type="button" class="btn sm" :disabled="yardPage === 0" @click="yardPage--">이전</button>
          <span>{{ yardPage + 1 }} / {{ pageCount }}</span>
          <button type="button" class="btn sm" :disabled="yardPage + 1 >= pageCount" @click="yardPage++">다음</button>
        </div>
      </div>
      <div class="yard-stage">
        <ShipViewer3D v-if="active && !detail.open" :fleet="yardHulls" @select="openDetail" />
      </div>
    </section>
    <HoverCard v-if="hp.pv.key && !detail.open" :pos="hp.pv.pos" :width="380" :height="340" @enter="hp.keep" @leave="hp.leave">
      <template v-for="h in [hulls.find((x) => x.hull_no === hp.pv.key)]" :key="hp.pv.key">
        <div v-if="h" class="pv">
          <div class="pvh"><b>{{ h.hull_no }} {{ h.hull_nm }}</b><span class="b b-info">{{ codeName('HULLSTAT', h.hull_status) }}</span></div>
          <div class="pvm">{{ codeName('SHIPTYPE', h.ship_type) }} · {{ h.owner_nm }} · {{ h.class_society }} · 도크 {{ dash(h.dock_no) }}</div>
          <div class="pvr"><span>진척</span><ProgressBar v-if="h.progress !== null" :value="h.progress" /><span v-else class="muted">계획 없음</span></div>
          <div class="pvr"><span>계약 / 인도</span>{{ h.contract_dt }} → {{ h.delivery_dt }}</div>
          <p v-if="hp.pv.error" class="muted">{{ hp.pv.error }}</p>
          <p v-else-if="!hp.pv.data" class="muted">불러오는 중…</p>
          <template v-else>
            <div class="pvr"><span>공정 {{ hp.pv.data.sum.plan_count }}건</span>
              <span class="chips"><span v-for="(n, s) in hp.pv.data.sum.plan_status" v-show="n" :key="s" class="chip"><i :style="{ background: `var(--c-${s})` }"></i>{{ codeName('PLANSTAT', s) }} {{ n }}</span></span>
            </div>
            <div class="pvr"><span>도면 {{ hp.pv.data.sum.drawing_count }}건</span>
              <span class="chips"><span v-for="(n, s) in hp.pv.data.sum.drawing_status" v-show="n" :key="s" class="chip">{{ codeName('DWGSTAT', s) }} {{ n }}</span></span>
            </div>
            <table v-if="hp.pv.data.ms.length" class="pvt">
              <thead><tr><th>주요 일정</th><th>계획</th><th>실적</th></tr></thead>
              <tbody><tr v-for="m in hp.pv.data.ms" :key="m.milestone_cd"><td>{{ m.name }}</td><td>{{ dash(m.plan_dt) }}</td><td>{{ dash(m.actual_dt) }}</td></tr></tbody>
            </table>
          </template>
          <div class="pvf muted">더블클릭하면 상세를 엽니다.</div>
        </div>
      </template>
    </HoverCard>
    <HullDetail v-if="active && detail.open" :hull-no="detail.no" :can-write="canWrite" @close="detail.open = false" @changed="load" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import { codeList, codeName, fail } from '../stores/session.js'
import { dash } from '../utils/date.js'
import PageHead from '../components/PageHead.vue'
import ProgressBar from '../components/ProgressBar.vue'
import HullDetail from './HullDetail.vue'
import ShipViewer3D from '../components/ShipViewer3D.vue'
import HoverCard from '../components/HoverCard.vue'
import { useHoverPreview } from '../utils/hoverPreview.js'

const props = defineProps({ active: { type: Boolean, default: true }, token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const f = reactive({ status: '', ship_type: '', q: '' })
const hulls = ref([])
const yardPage = ref(0)
const pageCount = computed(() => Math.ceil(hulls.value.length / 6))
const yardHulls = computed(() => hulls.value.slice(yardPage.value * 6, (yardPage.value + 1) * 6))
const loaded = ref(false)
const selected = ref(null)
const detail = reactive({ open: false, no: null })

async function load() {
  try {
    hulls.value = await api.get('/api/hulls', { ...f })
    yardPage.value = Math.min(yardPage.value, Math.max(0, pageCount.value - 1))
    hp.clear()
    loaded.value = true
  } catch (e) { fail(e) }
}
function resetFilter() {
  Object.assign(f, { status: '', ship_type: '', q: '' })
  load()
}
const hp = useHoverPreview(async (no) => {
  const [sum, ms] = await Promise.all([api.get(`/api/hulls/${no}/summary`), api.get(`/api/hulls/${no}/milestones`)])
  return { sum, ms }
})
function openDetail(no) {
  hp.close()
  if (no) selected.value = no
  Object.assign(detail, { open: true, no })
}
onMounted(load)
watch(() => props.ctx, load)
</script>

<style scoped>
.yard-section { width: 100%; margin-top: 16px; }
.yard-head, .yard-pages { display: flex; align-items: center; gap: 10px; }
.yard-head { justify-content: space-between; flex-wrap: wrap; margin-bottom: 10px; }
.yard-head h2, .yard-head p { margin: 0; }
.yard-head h2 { font-size: 18px; }
.yard-stage { min-width: 0; }
.fsel { width: 110px; }
.fq { width: 148px; }
.pcell { width: 150px; }
.total { margin-top: 8px; font-size: 12px; color: var(--muted); }
</style>
