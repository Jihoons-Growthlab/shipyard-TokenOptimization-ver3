<template>
  <div class="fg c2">
    <label class="f"><span>도면번호 *</span><input v-model.trim="model.drawing_no" name="drawing_no" :readonly="edit || readonly" /></label>
    <label class="f"><span>분야</span>
      <select v-model="model.discipline" name="discipline" :disabled="readonly">
        <option v-for="c in codeList('DWGDISC')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
    </label>
    <label class="f s2"><span>도면명 *</span><input v-model.trim="model.drawing_nm" name="drawing_nm" :readonly="readonly" /></label>
    <label class="f"><span>호선</span>
      <select v-model="model.hull_no" name="hull_no" :disabled="edit || readonly" @change="model.block_id = null">
        <option v-for="h in hullOpts" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
    </label>
    <label class="f"><span>블록</span>
      <select v-model="model.block_id" name="block_id" :disabled="readonly">
        <option :value="null">블록 없음</option>
        <option v-for="b in blockOpts" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option>
      </select>
    </label>
    <label class="f s2"><span>설계자</span>
      <select v-model="model.designer_emp_no" name="designer_emp_no" :disabled="readonly">
        <option :value="null">-</option>
        <option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ userLabel(u) }}</option>
      </select>
    </label>
    <slot />
  </div>
</template>

<script setup>
// 도면 등록·상세 공용 입력. model은 부모 소유 reactive 객체(drawing_no, drawing_nm, discipline, hull_no, block_id, designer_emp_no).
import { computed, ref, watch } from 'vue'
import { codeList, userLabel } from '../stores/session.js'
import { loadBlocks } from '../utils/drawing.js'

const props = defineProps({
  model: { type: Object, required: true },
  hulls: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
  edit: Boolean,
  readonly: Boolean,
  current: { type: Object, default: null }, // 상세의 현재 값(목록 권한이 없을 때 표시 보존)
})

const blocks = ref([])
let seq = 0
watch(() => props.model.hull_no, async (h) => {
  const s = ++seq
  const list = await loadBlocks(h)
  if (s === seq) blocks.value = list
}, { immediate: true })

const hullOpts = computed(() => {
  const c = props.current
  return c && !props.hulls.some((h) => h.hull_no === c.hull_no) ? [...props.hulls, { hull_no: c.hull_no, hull_nm: '' }] : props.hulls
})
const blockOpts = computed(() => {
  const c = props.current
  return c?.block_id && c.hull_no === props.model.hull_no && !blocks.value.some((b) => b.block_id === c.block_id)
    ? [...blocks.value, { block_id: c.block_id, block_cd: c.block_cd, block_nm: c.block_nm }] : blocks.value
})
</script>
