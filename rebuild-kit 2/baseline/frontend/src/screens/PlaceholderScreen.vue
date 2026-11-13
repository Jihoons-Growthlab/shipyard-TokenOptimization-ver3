<template>
  <PageHead :title="title" :readonly="!canWrite" />
</template>

<script setup>
import PageHead from '../components/PageHead.vue'

defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })
</script>
