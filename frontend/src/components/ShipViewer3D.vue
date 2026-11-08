<template>
  <div class="v3d">
    <div class="viewer" @contextmenu.prevent>
      <canvas :id="canvasId" :key="attempt" ref="canvasEl" class="ucanvas" tabindex="-1"></canvas>
      <div v-if="state === 'loading'" class="ovl">
        <p>3D 뷰어 불러오는 중…</p>
        <div class="pbar"><i :style="{ width: Math.round(progress * 100) + '%' }"></i></div>
      </div>
      <div v-else-if="state === 'error'" class="ovl fail">
        <p><b>3D 뷰어를 불러오지 못했습니다.</b></p>
        <p class="why">{{ reason }}</p>
        <button class="btn" type="button" @click="retry">재시도</button>
      </div>
    </div>
    <aside class="side">
      <section class="card">
        <h4>샘플 호선 3D 뷰어</h4>
        <p class="model">Demo Ship 01</p>
        <div class="note warn">예시 모델 — 실제 호선 형상과 다름</div>
      </section>
      <section class="card">
        <h4>시점</h4>
        <div class="views">
          <button v-for="v in VIEW_BTNS" :key="v.id" class="btn" type="button" :disabled="state !== 'ready'" @click="handle?.setView(v.id)">{{ v.label }}</button>
        </div>
      </section>
      <section class="card">
        <h4>조작 안내</h4>
        <dl class="guide">
          <dt>왼쪽 드래그</dt><dd>회전</dd>
          <dt>휠</dt><dd>확대·축소</dd>
          <dt>오른쪽 드래그</dt><dd>화면 이동</dd>
        </dl>
      </section>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { startViewer } from '../utils/unityViewer.js'

const props = defineProps({ options: { type: Object, default: () => ({}) } })

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

function begin() {
  state.value = 'loading'
  progress.value = 0
  reason.value = ''
  const h = startViewer(canvasEl.value, {
    onProgress: (p) => { if (handle.value === h) progress.value = p },
    onReady: () => { if (handle.value === h) state.value = 'ready' },
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

onMounted(begin)
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
.model { margin: 0 0 10px; font-size: 15px; font-weight: 700; }
.views { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.guide { display: grid; grid-template-columns: 95px 1fr; gap: 6px 0; margin: 0; font-size: 12px; }
.guide dd { margin: 0; }
@media (max-width: 760px) {
  .v3d { grid-template-columns: 1fr; grid-template-rows: minmax(260px, 1fr) auto; height: auto; }
  .viewer { min-height: 260px; height: 60vh; }
  .side { max-height: 40vh; overflow: auto; }
}
</style>
