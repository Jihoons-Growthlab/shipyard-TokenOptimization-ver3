<template>
  <div class="pbar"><i :style="{ width: pct + '%' }"></i><b>{{ pct }}%</b></div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ value: { type: Number, default: 0 } })
const pct = computed(() => Math.max(0, Math.min(100, Math.round(Number(props.value) || 0))))
</script>
