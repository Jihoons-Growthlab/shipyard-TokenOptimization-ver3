<template>
  <div class="v3d" :class="{ 'fleet-view': fleet }">
    <div class="viewer" @contextmenu.prevent>
      <canvas :id="canvasId" :key="attempt" ref="canvasEl" class="ucanvas" tabindex="-1" @shipviewer-hover="hovering = $event.detail"
        @shipyard-hover="fleetSlot = $event.detail" @shipyard-select="selectSlot($event.detail)"
        @pointerleave="pointerInside = false" @pointerenter="pointerInside = true"></canvas>
      <div v-if="state === 'loading'" class="ovl">
        <p>3D 뷰어 불러오는 중…</p>
        <div class="pbar"><i :style="{ width: Math.round(progress * 100) + '%' }"></i></div>
      </div>
      <div v-else-if="state === 'error'" class="ovl fail">
        <p><b>3D 뷰어를 불러오지 못했습니다.</b></p>
        <p class="why">{{ reason }}</p>
        <button class="btn" type="button" @click="retry">재시도</button>
      </div>
      <div v-if="state === 'ready' && pointerInside && hoveredHull" class="twin-hover">
        <strong>{{ hoveredHull.hull_no }} · {{ hoveredHull.hull_nm || '호선' }}</strong>
        <span>{{ berth(fleetSlot) }} · {{ codeName('HULLSTAT', hoveredHull.hull_status) || '상태 미등록' }}</span>
        <dl class="hover-details">
          <dt>진척률</dt><dd>{{ hoveredHull.progress == null ? '계획 없음' : hoveredHull.progress + '%' }}</dd>
          <dt>지연 공정</dt><dd>{{ hoveredHull.delay_count ?? 0 }}건</dd>
          <dt>인도 예정</dt><dd>{{ hoveredHull.delivery_dt || '미정' }}</dd>
        </dl>
        <span>클릭하여 상세 보기</span>
      </div>
      <div v-if="state === 'ready' && hovering && pointerInside && hull" class="twin-hover">
        <strong>{{ hull.hull_no }} · {{ hull.hull_nm || '호선' }}</strong>
        <span>{{ codeName('HULLSTAT', hull.hull_status) }} · 진척률 {{ progressLabel }}</span>
      </div>
    </div>
    <aside v-if="!fleet" class="side">
      <section class="card">
        <h4>호선 디지털 트윈</h4>
        <template v-if="hull">
          <p class="model">{{ hull.hull_no }} · {{ hull.hull_nm || '호선' }}</p>
          <dl class="guide">
            <dt>상태</dt><dd>{{ codeName('HULLSTAT', hull.hull_status) }}</dd>
            <dt>도크</dt><dd>{{ hull.dock_no || '미지정' }}</dd>
            <dt>진척률</dt><dd>{{ progressLabel }}</dd>
            <dt>지연 공정</dt><dd>{{ hull.delay_count }}건</dd>
            <dt>인도 예정</dt><dd>{{ hull.delivery_dt || '미정' }}</dd>
          </dl>
        </template>
        <p v-if="dataError" role="status">{{ dataError }}</p>
        <button v-if="hullNo" class="btn refresh" type="button" :disabled="refreshing" @click="refresh">
          {{ refreshing ? '조회 중…' : '호선 정보 새로고침' }}
        </button>
        <p class="muted">가상 조선소 · 예시 선체 형상</p>
      </section>
      <section class="card view-controls" aria-label="시점 선택">
        <h4>시점</h4>
        <div class="views">
          <button v-for="v in VIEW_BTNS" :key="v.id" class="btn" type="button" :disabled="state !== 'ready'" @click="handle?.setView(v.id)">{{ v.label }}</button>
        </div>
      </section>
      <section class="card">
        <h4>조작 안내</h4>
        <dl class="guide">
          <dt>선체에 마우스</dt><dd>호선 정보</dd>
          <dt>왼쪽 드래그</dt><dd>회전</dd>
          <dt>휠</dt><dd>확대·축소</dd>
          <dt>오른쪽 드래그</dt><dd>화면 이동</dd>
        </dl>
      </section>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { api } from '../api/client.js'
import { codeName } from '../stores/session.js'
import { startViewer } from '../utils/unityViewer.js'

const props = defineProps({ hullNo: String, fleet: Array, options: { type: Object, default: () => ({}) } })

const emit = defineEmits(['select'])
const fleetSlot = ref(-1)
const hoveredHull = computed(() => props.fleet?.[fleetSlot.value])
const berth = (index) => index < 3 ? '드라이도크' : '안벽'
function selectSlot(index) {
  const item = props.fleet?.[index]
  if (item) emit('select', item.hull_no)
}
watch(() => props.fleet, (fleet) => {
  fleetSlot.value = -1
  if (fleet) handle.value?.setFleet(fleet.length)
})

const VIEW_BTNS = [
  { id: 'front', label: '정면' },
  { id: 'side', label: '측면' },
  { id: 'top', label: '상단' },
  { id: 'reset', label: '초기화' },
]
const attempt = ref(0)
const canvasId = computed(() => `ship-viewer-canvas-${attempt.value}`)
const canvasEl = ref(null)
const state = ref('loading')
const progress = ref(0)
const reason = ref('')
const handle = shallowRef(null)
let alive = true
const hull = ref(null)
const refreshing = ref(false)
const dataError = ref('')
const hovering = ref(false)
const pointerInside = ref(false)
const progressLabel = computed(() => hull.value?.progress == null ? '계획 없음' : `${hull.value.progress}%`)

async function refresh() {
  if (!props.hullNo || refreshing.value) return
  refreshing.value = true
  dataError.value = ''
  try {
    hull.value = await api.get(`/api/hulls/${encodeURIComponent(props.hullNo)}`)
  } catch {
    dataError.value = '호선 정보를 불러오지 못했습니다.'
  } finally {
    refreshing.value = false
  }
}

function begin() {
  fleetSlot.value = -1
  hovering.value = false
  pointerInside.value = false
  state.value = 'loading'
  progress.value = 0
  reason.value = ''
  const h = startViewer(canvasEl.value, {
    onProgress: (p) => { if (handle.value === h) progress.value = p },
    onReady: () => {
      if (handle.value !== h) return
      state.value = 'ready'
      if (props.fleet) h.setFleet(props.fleet.length)
    },
    onError: (msg) => { if (handle.value === h) { reason.value = msg; state.value = 'error' } },
  }, props.options)
  handle.value = h
}

async function retry() {
  handle.value?.stop()
  handle.value = null
  attempt.value++ // 재시도는 새 canvas
  await nextTick()
  if (alive) begin()
}

onMounted(() => { begin(); refresh() })
onBeforeUnmount(() => {
  alive = false
  handle.value?.stop()
  handle.value = null
})

defineExpose({ handle, state })
</script>

<style scoped>
.v3d { display: grid; grid-template-columns: 1fr 260px; gap: 12px; height: calc(94vh - 150px); min-height: 360px; }
.viewer { position: relative; border: 1px solid var(--line); border-radius: 8px; background: #dde4ee; overflow: hidden; min-height: 260px; }
.ucanvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; outline: none; }
.ovl { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; background: #dde4ee; color: var(--muted); text-align: center; padding: 16px; }
.ovl p { margin: 0; }
.ovl .pbar { width: 220px; height: 6px; background: #c7d0dc; border-radius: 3px; overflow: hidden; }
.ovl .pbar i { display: block; height: 100%; background: var(--pri); transition: width .2s; }
.fail { color: var(--text, #1f2937); }
.why { font-size: 12px; color: var(--muted); }
.side { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.side .card { padding: 14px; }
.side h4 { margin: 0 0 10px; font-size: 13px; }
.twin-hover { pointer-events: none; position: absolute; top: 14px; left: 14px; display: grid; gap: 4px; padding: 10px 14px; border-radius: 8px; background: #172a40; color: #fff; box-shadow: 0 4px 14px #0003; }
.twin-hover span { color: #d2e4f7; font-size: 12px; }
.refresh { margin-top: 12px; }
.model { margin: 0 0 10px; font-size: 15px; font-weight: 700; }
.views { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.guide { display: grid; grid-template-columns: 95px 1fr; gap: 6px 0; margin: 0; font-size: 12px; }
.guide dd { margin: 0; }
.fleet-view { --yard-height: clamp(260px, 32vw, 410px); grid-template-columns: minmax(0, 1fr); height: auto; min-height: 0; }
.fleet-view .viewer { height: var(--yard-height); min-height: 0; }
@media (max-width: 760px) {
  .fleet-view { --yard-height: clamp(210px, 50vw, 320px); grid-template-columns: minmax(0, 1fr); }
}
.fleet-view .twin-hover { max-width: calc(100% - 28px); overflow-wrap: anywhere; }
.hover-details { display: grid; grid-template-columns: auto 1fr; gap: 3px 10px; font-size: 12px; margin: 3px 0; }
.hover-details dd { margin: 0; }
@media (max-width: 760px) {
  .v3d:not(.fleet-view) { grid-template-columns: 1fr; grid-template-rows: minmax(260px, 1fr) auto; height: auto; }
  .v3d:not(.fleet-view) .viewer { min-height: 260px; height: 60vh; }
  .v3d:not(.fleet-view) .side { max-height: 40vh; overflow: auto; }
}
</style>
