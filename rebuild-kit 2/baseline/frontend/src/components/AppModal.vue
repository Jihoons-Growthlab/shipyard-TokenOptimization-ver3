<template>
  <teleport to="body">
    <div class="mbg" @mousedown.self="$emit('close')">
      <div class="modal" :class="size" role="dialog" aria-modal="true">
        <header>
          <h3>{{ title }}</h3>
          <button type="button" class="mclose" @click="$emit('close')">닫기 ✕</button>
        </header>
        <div class="mbody"><slot /></div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'

defineProps({ title: { type: String, default: '' }, size: { type: String, default: '' } })
const emit = defineEmits(['close'])
const onKey = (e) => { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>
