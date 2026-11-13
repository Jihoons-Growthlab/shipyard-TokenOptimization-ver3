<template>
  <Teleport to="body">
    <div class="hcard" :style="style" @mouseenter="$emit('enter')" @mouseleave="$emit('leave')">
      <slot />
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'

// pos: {x, top, bottom} — 행 아래에 붙이고, 아래 공간이 부족하면 위로 띄운다.
const props = defineProps({ pos: Object, width: { type: Number, default: 360 }, height: { type: Number, default: 320 } })
defineEmits(['enter', 'leave'])

const style = computed(() => {
  const { x, top, bottom } = props.pos
  const vw = window.innerWidth
  const vh = window.innerHeight
  const left = Math.max(8, Math.min(x - 40, vw - props.width - 8))
  const below = bottom + 4 + props.height <= vh
  return below
    ? { left: `${left}px`, top: `${bottom + 4}px`, width: `${props.width}px` }
    : { left: `${left}px`, bottom: `${vh - top + 4}px`, width: `${props.width}px` }
})
</script>

<style scoped>
.hcard {
  position: fixed; z-index: 900; background: #fff; border: 1px solid var(--line); border-radius: 8px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, .18), 0 2px 6px rgba(15, 23, 42, .06); padding: 12px 14px; font-size: 12.5px; max-height: 70vh; overflow: auto;
  border-radius: 10px; animation: rise-in .18s var(--ease) both;
}
</style>
