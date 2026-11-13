<template>
  <div class="ph">
    <h2>{{ title }}</h2>
    <p v-if="desc">{{ desc }}</p>
    <span v-if="readonly" class="ro">조회 전용</span>
    <slot />
  </div>
</template>

<script setup>
defineProps({ title: String, desc: String, readonly: Boolean })
</script>
