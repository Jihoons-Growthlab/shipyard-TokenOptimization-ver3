<template>
  <span class="b" :class="'b-' + code">{{ codeName(group, code) }}</span>
</template>

<script setup>
import { codeName } from '../stores/session.js'

/** group: PLANSTAT | DWGSTAT */
defineProps({ group: { type: String, default: 'PLANSTAT' }, code: { type: String, default: '' } })
</script>
