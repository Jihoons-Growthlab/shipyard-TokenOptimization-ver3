<template>
  <!-- 챗봇 보고서 작성(명세 외 요청 기능): 범위·형식을 고르면 MCP build_report 도구가 파일을 만든다. -->
  <div class="crep">
    <template v-if="!result">
      <div class="lbl">범위</div>
      <div class="opts">
        <button type="button" :class="{ on: hullNo === '' }" :disabled="busy" @click="hullNo = ''">전체 호선</button>
        <button v-for="h in hulls" :key="h.hull_no" type="button" :class="{ on: hullNo === h.hull_no }" :disabled="busy" :title="h.hull_nm" @click="hullNo = h.hull_no">
          {{ h.hull_no }}
        </button>
      </div>
      <div class="lbl">형식</div>
      <div class="fmt">
        <button type="button" :class="{ on: format === 'pdf' }" :disabled="busy" @click="format = 'pdf'"><b class="ico pdf">PDF</b>문서로 보기·인쇄</button>
        <button type="button" :class="{ on: format === 'xlsx' }" :disabled="busy" @click="format = 'xlsx'"><b class="ico xls">XLS</b>Excel로 편집</button>
      </div>
      <button type="button" class="go" :disabled="busy" @click="create">{{ busy ? '보고서를 만드는 중…' : '보고서 작성하기' }}</button>
      <p v-if="error" class="err" role="alert">{{ error }}</p>
    </template>
    <template v-else>
      <div class="done">
        <b class="ico" :class="result.format === 'pdf' ? 'pdf' : 'xls'">{{ result.format === 'pdf' ? 'PDF' : 'XLS' }}</b>
        <div class="meta">
          <strong>{{ result.title }}</strong>
          <small>{{ result.filename }} · {{ sizeText }}</small>
          <small>호선 {{ result.summary.hulls }} · 공정 {{ result.summary.plans }} · 지연 {{ result.summary.delay }} · 도면 {{ result.summary.drawings }}</small>
        </div>
      </div>
      <div class="row">
        <button type="button" class="go" :disabled="busy" @click="download">{{ busy ? '내려받는 중…' : '다운로드' }}</button>
        <button type="button" class="again" :disabled="busy" @click="result = null">다른 보고서</button>
      </div>
      <p v-if="error" class="err" role="alert">{{ error }}</p>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { api } from '../api/client.js'

const emit = defineEmits(['update'])
const hulls = ref([])
const hullNo = ref('')
const format = ref('pdf')
const busy = ref(false)
const error = ref('')
const result = ref(null)

const sizeText = computed(() => {
  const n = result.value?.size || 0
  return n >= 1048576 ? `${(n / 1048576).toFixed(1)}MB` : `${Math.max(1, Math.round(n / 1024))}KB`
})

async function create() {
  busy.value = true
  error.value = ''
  try {
    result.value = await api.post('/api/chat/report', { format: format.value, hull_no: hullNo.value || null })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
    nextTick(() => emit('update'))
  }
}
async function download() {
  busy.value = true
  error.value = ''
  try {
    const blob = await api.blob(result.value.download_url)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = result.value.filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
onMounted(async () => {
  try { hulls.value = (await api.get('/api/chat/report/options')).hulls } catch (e) { error.value = e.message }
  nextTick(() => emit('update'))
})
</script>

<style scoped>
.crep { margin: 0 0 10px; padding: 10px; border: 1px solid #acdbe4; border-radius: 10px; background: #f7fcfd; display: grid; gap: 6px; animation: rise-in .2s ease-out both; }
.lbl { font-size: 11.5px; color: #4b6b80; font-weight: 600; }
.opts { display: flex; flex-wrap: wrap; gap: 5px; }
.opts button, .fmt button, .again { border: 1px solid #a6cbd8; border-radius: 999px; padding: 4px 10px; background: #fff; color: #18364d; cursor: pointer; font: inherit; font-size: 12.5px;
  transition: background .15s, border-color .15s, color .15s; }
.opts button.on, .fmt button.on { background: #205471; border-color: #205471; color: #fff; }
.fmt { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.fmt button { border-radius: 8px; display: flex; align-items: center; gap: 6px; padding: 6px 8px; text-align: left; }
.ico { display: inline-grid; place-items: center; width: 30px; height: 22px; border-radius: 4px; font-size: 9.5px; font-weight: 800; color: #fff; flex: none; }
.ico.pdf { background: #dc2626; } .ico.xls { background: #16a34a; }
.go { border: 0; border-radius: 8px; background: #205471; color: #fff; padding: 8px 10px; cursor: pointer; font: inherit; font-weight: 700; transition: filter .15s; }
.go:hover:not(:disabled) { filter: brightness(1.12); }
.go:disabled, .opts button:disabled, .fmt button:disabled { opacity: .6; cursor: default; }
.done { display: flex; gap: 10px; align-items: center; }
.done .ico { width: 38px; height: 46px; font-size: 11px; border-radius: 6px; }
.meta { display: grid; gap: 2px; min-width: 0; }
.meta small { color: #4b6b80; overflow-wrap: anywhere; }
.row { display: grid; grid-template-columns: 1fr auto; gap: 6px; }
.again { border-radius: 8px; }
.err { margin: 0; padding: 6px 8px; border-radius: 6px; background: #fff0ed; color: #8c2e21; font-size: 12.5px; }
</style>
