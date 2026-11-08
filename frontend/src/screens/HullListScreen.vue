<template>
  <div>
    <PageHead title="호선 목록" desc="행을 더블클릭하거나 [상세]를 누르면 호선 상세 팝업이 열립니다." :readonly="!canWrite" />
    <form class="toolbar" @submit.prevent="load">
      <select v-model="f.status" class="fsel" aria-label="상태">
        <option value="">상태 전체</option>
        <option v-for="c in codeList('HULLSTAT')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <select v-model="f.ship_type" class="fsel" aria-label="선종">
        <option value="">선종 전체</option>
        <option v-for="c in codeList('SHIPTYPE')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <input v-model.trim="f.q" class="fq" placeholder="호선번호/호선명/선주" />
      <button class="btn pri" type="submit">조회</button>
      <button class="btn" type="button" @click="resetFilter">초기화</button>
      <div class="grow"></div>
      <button v-if="canWrite" class="btn pri" type="button" @click="openDetail(null)">+ 호선 등록</button>
    </form>
    <div class="tw">
      <table class="t hull-table">
        <thead>
          <tr>
            <th>호선번호</th><th>호선명</th><th>선종</th><th>상태</th><th>선주</th><th>선급</th><th>도크</th>
            <th>계약일</th><th>인도예정</th><th>진척률</th><th class="num">지연</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in hulls" :key="h.hull_no" class="click" :class="{ on: selected === h.hull_no }"
            @click="selected = h.hull_no" @dblclick="openDetail(h.hull_no)">
            <td><b>{{ h.hull_no }}</b></td>
            <td>{{ h.hull_nm }}</td>
            <td>{{ codeName('SHIPTYPE', h.ship_type) }}</td>
            <td><span class="b b-info">{{ codeName('HULLSTAT', h.hull_status) }}</span></td>
            <td>{{ h.owner_nm }}</td>
            <td>{{ h.class_society }}</td>
            <td>{{ dash(h.dock_no) }}</td>
            <td>{{ h.contract_dt }}</td>
            <td>{{ h.delivery_dt }}</td>
            <td class="pcell"><ProgressBar v-if="h.progress !== null" :value="h.progress" /><span v-else class="muted">계획 없음</span></td>
            <td class="num">{{ h.delay_count || '-' }}</td>
            <td><button class="btn sm" type="button" @click.stop="openDetail(h.hull_no)">상세</button></td>
          </tr>
          <tr v-if="loaded && !hulls.length"><td colspan="12" class="empty">조회된 호선이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="total">총 {{ hulls.length }}척</div>
    <HullDetail v-if="detail.open" :hull-no="detail.no" :can-write="canWrite" @close="detail.open = false" @changed="load" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import { codeList, codeName, fail } from '../stores/session.js'
import { dash } from '../utils/date.js'
import PageHead from '../components/PageHead.vue'
import ProgressBar from '../components/ProgressBar.vue'
import HullDetail from './HullDetail.vue'

defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const f = reactive({ status: '', ship_type: '', q: '' })
const hulls = ref([])
const loaded = ref(false)
const selected = ref(null)
const detail = reactive({ open: false, no: null })

async function load() {
  try {
    hulls.value = await api.get('/api/hulls', { ...f })
    loaded.value = true
  } catch (e) { fail(e) }
}
function resetFilter() {
  Object.assign(f, { status: '', ship_type: '', q: '' })
  load()
}
function openDetail(no) {
  if (no) selected.value = no
  Object.assign(detail, { open: true, no })
}
onMounted(load)
</script>

<style scoped>
.fsel { width: 110px; }
.fq { width: 148px; }
.pcell { width: 150px; }
.total { margin-top: 8px; font-size: 12px; color: var(--muted); }
</style>
