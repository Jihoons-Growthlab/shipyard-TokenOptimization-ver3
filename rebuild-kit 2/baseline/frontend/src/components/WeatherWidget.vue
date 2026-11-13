<template>
  <div class="wx">
    <select v-model="region" aria-label="지역" @change="changeRegion">
      <option v-for="r in REGIONS" :key="r" :value="r">{{ r }}</option>
    </select>
    <template v-if="data">
      <span class="ico">{{ icon(data.condition) }}</span>
      <b class="temp">{{ data.tempC }}℃</b>
      <span>{{ data.condition }}</span>
      <span>습도 {{ data.humidity }}% · 바람 {{ data.windMs }}m/s</span>
      <span class="src" :class="data.source === 'LIVE' ? 'live' : 'sample'">{{ data.source === 'LIVE' ? 'LIVE' : '샘플' }}</span>
    </template>
    <span v-else-if="failed">날씨 조회 실패</span>
    <span v-else>날씨 조회 중…</span>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api/client.js'

const REGIONS = ['울산', '거제', '목포']
const REGION_KEY = 'swp_region'
const REFRESH_MS = 10 * 60 * 1000

function savedRegion() {
  try { const r = localStorage.getItem(REGION_KEY); return REGIONS.includes(r) ? r : '울산' } catch { return '울산' }
}

const region = ref(savedRegion())
const data = ref(null)
const failed = ref(false)
let seq = 0
let timer = null

function icon(c = '') {
  if (c.includes('맑')) return '☀️'
  if (c.includes('구름')) return '⛅'
  if (c.includes('흐')) return '☁️'
  if (c.includes('눈')) return '❄️'
  if (c.includes('비')) return '🌧️'
  return '🌤️'
}

async function load() {
  const my = ++seq
  try {
    const r = await api.get('/api/weather', { region: region.value })
    if (my !== seq) return
    data.value = r
    failed.value = false
  } catch {
    if (my !== seq) return
    data.value = null
    failed.value = true
  }
}

function changeRegion() {
  try { localStorage.setItem(REGION_KEY, region.value) } catch { /* 무시 */ }
  data.value = null
  failed.value = false
  load()
}

onMounted(() => { load(); timer = setInterval(load, REFRESH_MS) })
onUnmounted(() => { seq++; clearInterval(timer) })
defineExpose({ load })
</script>

<style scoped>
.wx { display: flex; align-items: center; gap: 8px; background: var(--navy2); border-radius: 18px; padding: 4px 12px; font-size: 12px; white-space: nowrap; }
.wx select { height: 26px; padding: 0 4px; background: var(--navy); color: #fff; border: 1px solid #3b5a8c; font-size: 12px; }
.temp { font-size: 14px; }
.src { font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 700; }
.src.sample { background: #f59e0b; color: #3b2600; }
.src.live { background: #22c55e; color: #052e16; }
</style>
