<template>
  <TransitionGroup name="toast" tag="div" class="toasts" aria-live="polite">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.kind">{{ t.message }}</div>
  </TransitionGroup>
</template>

<script setup>
import { toasts } from '../stores/session.js'
</script>
