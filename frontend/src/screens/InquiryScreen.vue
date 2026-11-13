<template>
  <div class="iq">
    <PageHead title="건의·문의" :desc="admin ? '회원의 건의·문의를 확인하고 상태와 답변을 처리합니다.' : '시스템 개선 건의나 사용 문의를 남겨 주세요. 관리자가 확인 후 답변합니다.'" />
    <form class="toolbar" @submit.prevent="load">
      <div class="chips">
        <button v-for="c in statusChips" :key="c.code" type="button" class="chip" :class="{ on: f.status === c.code }" @click="setStatus(c.code)">
          {{ c.name }} <b>{{ c.count }}</b>
        </button>
      </div>
      <input v-model.trim="f.q" class="fq" placeholder="제목/내용/작성자" />
      <button class="btn pri" type="submit">조회</button>
      <label v-if="admin" class="chk"><input v-model="f.mine" type="checkbox" @change="load" />내 글만</label>
      <div class="grow"></div>
      <button class="btn pri" type="button" @click="startNew">+ 새 글 작성</button>
    </form>

    <div class="split">
      <div class="tw list">
        <table class="t">
          <thead><tr><th class="num">No</th><th>상태</th><th>분류</th><th>제목</th><th v-if="admin">작성자</th><th>작성일</th><th>답변일</th></tr></thead>
          <tbody>
            <tr v-for="x in items" :key="x.inquiry_id" class="click" :class="{ on: sel === x.inquiry_id }" @click="open(x)">
              <td class="num muted">{{ x.inquiry_id }}</td>
              <td><span class="b" :class="STAT_CLS[x.status]">{{ meta.statuses[x.status] }}</span></td>
              <td><span class="cat" :class="x.category">{{ meta.categories[x.category] }}</span></td>
              <td class="ttl">{{ x.title }}</td>
              <td v-if="admin">{{ x.create_user_nm || '-' }}</td>
              <td class="muted">{{ fmtUtc(x.create_dt).slice(0, 10) }}</td>
              <td class="muted">{{ x.answer_dt ? fmtUtc(x.answer_dt).slice(0, 10) : '-' }}</td>
            </tr>
            <tr v-if="loaded && !items.length"><td :colspan="admin ? 7 : 6" class="empty">{{ f.status || f.q ? '조건에 맞는 글이 없습니다.' : '아직 작성한 글이 없습니다.' }}</td></tr>
          </tbody>
        </table>
      </div>

      <section class="card panel">
        <template v-if="mode === 'new' || mode === 'edit'">
          <h3>{{ mode === 'new' ? '새 글 작성' : '글 수정' }}</h3>
          <form class="fg" @submit.prevent="submit">
            <label class="f"><span>분류 *</span>
              <select v-model="fm.category" name="category">
                <option v-for="(v, k) in meta.categories" :key="k" :value="k">{{ v }}</option>
              </select>
            </label>
            <label class="f"><span>제목 *</span><input v-model="fm.title" name="title" maxlength="200" placeholder="한 줄로 요약해 주세요" /></label>
            <label class="f"><span>내용 *</span><textarea v-model="fm.content" name="content" rows="10" maxlength="5000" placeholder="어떤 화면에서 무엇을 했을 때 어떤 일이 있었는지, 또는 원하는 기능을 적어 주세요."></textarea></label>
            <div class="bar-row">
              <button class="btn pri" type="submit" :disabled="busy">{{ mode === 'new' ? '등록' : '저장' }}</button>
              <button class="btn" type="button" @click="mode === 'edit' ? (mode = 'view') : close()">취소</button>
            </div>
          </form>
        </template>

        <template v-else-if="mode === 'view' && cur">
          <div class="vh">
            <span class="b" :class="STAT_CLS[cur.status]">{{ meta.statuses[cur.status] }}</span>
            <span class="cat" :class="cur.category">{{ meta.categories[cur.category] }}</span>
            <span class="muted">No.{{ cur.inquiry_id }}</span>
          </div>
          <h3 class="vt">{{ cur.title }}</h3>
          <div class="muted vm">{{ cur.create_user_nm || '-' }} · {{ fmtUtc(cur.create_dt) }}<template v-if="cur.modify_dt"> · 수정 {{ fmtUtc(cur.modify_dt) }}</template></div>
          <div class="body">{{ cur.content }}</div>

          <div v-if="cur.answer" class="answer">
            <div class="ah"><b>관리자 답변</b><span class="muted">{{ cur.answer_user_nm || '-' }} · {{ fmtUtc(cur.answer_dt) }}</span></div>
            <div class="body">{{ cur.answer }}</div>
          </div>
          <p v-else-if="!admin" class="muted wait">관리자가 확인 중입니다. 답변이 등록되면 여기에 표시됩니다.</p>

          <div v-if="cur.mine && cur.status === 'OPEN'" class="bar-row">
            <button class="btn" type="button" @click="startEdit">수정</button>
            <button class="btn danger" type="button" :disabled="busy" @click="remove">삭제</button>
          </div>

          <form v-if="admin" class="proc" @submit.prevent="process">
            <h4>처리</h4>
            <div class="steps">
              <button v-for="(v, k) in meta.statuses" :key="k" type="button" class="step" :class="[k, { on: pf.status === k }]" @click="pf.status = k">{{ v }}</button>
            </div>
            <label class="f"><span>답변 {{ ['DONE', 'REJECTED'].includes(pf.status) ? '*' : '(선택)' }}</span>
              <textarea v-model="pf.answer" name="answer" rows="5" maxlength="5000" placeholder="작성자에게 보일 답변"></textarea>
            </label>
            <div class="bar-row">
              <button class="btn pri" type="submit" :disabled="busy">처리 저장</button>
              <button class="btn danger" type="button" :disabled="busy" @click="remove">삭제</button>
            </div>
          </form>
        </template>

        <div v-else class="emptyp">
          <p><b>{{ admin ? '목록에서 글을 선택해 처리하세요.' : '목록에서 글을 선택하거나 새 글을 작성하세요.' }}</b></p>
          <p class="muted">오류 신고 · 기능 건의 · 사용 문의 · 기타</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api/client.js'
import { fail, toast } from '../stores/session.js'
import { fmtUtc } from '../utils/date.js'
import PageHead from '../components/PageHead.vue'

const props = defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const STAT_CLS = { OPEN: 'b-info', IN_PROGRESS: 'b-warn', DONE: 'b-ok', REJECTED: 'b-bad' }
const f = reactive({ status: '', q: '', mine: false })
const items = ref([])
const counts = ref({})
const meta = reactive({ categories: {}, statuses: {} })
const admin = ref(false)
const loaded = ref(false)
const busy = ref(false)
const sel = ref(null)
const cur = ref(null)
const mode = ref('') // '' | 'new' | 'edit' | 'view'
const fm = reactive({ category: 'FEATURE', title: '', content: '' })
const pf = reactive({ status: 'OPEN', answer: '' })

const statusChips = computed(() => {
  const all = Object.values(counts.value).reduce((a, b) => a + b, 0)
  return [{ code: '', name: '전체', count: all }, ...Object.entries(meta.statuses).map(([code, name]) => ({ code, name, count: counts.value[code] || 0 }))]
})

async function load() {
  try {
    const r = await api.get('/api/inquiries', { status: f.status || undefined, q: f.q || undefined, mine: f.mine || undefined })
    items.value = r.items
    counts.value = r.counts
    admin.value = r.is_admin
    Object.assign(meta, { categories: r.categories, statuses: r.statuses })
    loaded.value = true
  } catch (e) { fail(e) }
}
function setStatus(code) {
  f.status = code
  load()
}
function show(x) {
  cur.value = x
  sel.value = x.inquiry_id
  mode.value = 'view'
  Object.assign(pf, { status: x.status, answer: x.answer || '' })
}
async function open(x) {
  try { show(await api.get(`/api/inquiries/${x.inquiry_id}`)) } catch (e) { fail(e) }
}
function close() {
  mode.value = ''
  sel.value = null
  cur.value = null
}
function startNew() {
  close()
  Object.assign(fm, { category: 'FEATURE', title: '', content: '' })
  mode.value = 'new'
}
function startEdit() {
  Object.assign(fm, { category: cur.value.category, title: cur.value.title, content: cur.value.content })
  mode.value = 'edit'
}
async function submit() {
  busy.value = true
  try {
    const body = { ...fm }
    const r = mode.value === 'new' ? await api.post('/api/inquiries', body) : await api.patch(`/api/inquiries/${cur.value.inquiry_id}`, body)
    toast(mode.value === 'new' ? '등록되었습니다. 관리자가 확인 후 답변합니다.' : '저장되었습니다.', 'success')
    await load()
    show(r)
  } catch (e) { fail(e) } finally { busy.value = false }
}
async function process() {
  busy.value = true
  try {
    const r = await api.patch(`/api/inquiries/${cur.value.inquiry_id}`, { status: pf.status, answer: pf.answer })
    toast('처리 내용을 저장했습니다.', 'success')
    await load()
    show(r)
  } catch (e) { fail(e) } finally { busy.value = false }
}
async function remove() {
  if (!window.confirm(`"${cur.value.title}" 글을 삭제합니다.`)) return
  busy.value = true
  try {
    await api.del(`/api/inquiries/${cur.value.inquiry_id}`)
    toast('삭제되었습니다.', 'success')
    close()
    await load()
  } catch (e) { fail(e) } finally { busy.value = false }
}
onMounted(load)
watch(() => props.ctx, load)
</script>

<style scoped>
.iq { height: 100%; display: flex; flex-direction: column; }
.fq { width: 180px; }
.chips { display: flex; gap: 4px; background: #e8ecf2; padding: 3px; border-radius: 8px; }
.chip { border: 0; background: transparent; height: 26px; padding: 0 10px; border-radius: 6px; font: inherit; font-size: 12.5px; color: var(--muted); cursor: pointer;
  transition: background var(--t-fast), color var(--t-fast), box-shadow var(--t-fast); }
.chip b { margin-left: 3px; font-size: 11px; color: inherit; }
.chip:hover { color: var(--ink); }
.chip.on { background: #fff; color: var(--pri-d); font-weight: 700; box-shadow: var(--shadow-sm); }
.split { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 460px; gap: 12px; }
.list { min-height: 0; }
.ttl { max-width: 360px; overflow: hidden; text-overflow: ellipsis; font-weight: 600; }
.cat { font-size: 11.5px; padding: 1px 7px; border-radius: 4px; background: #f1f5f9; color: #475569; white-space: nowrap; }
.cat.BUG { background: #fee2e2; color: #b91c1c; } .cat.FEATURE { background: #ede9fe; color: #6d28d9; }
.cat.QUESTION { background: #e0f2fe; color: #0369a1; }
.panel { margin: 0; min-height: 0; overflow: auto; animation: rise-in .25s var(--ease) both; }
.panel .fg { grid-template-columns: 1fr; }
.panel textarea { width: 100%; }
.vh { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.vh .muted { margin-left: auto; font-size: 12px; }
.vt { font-size: 15px !important; display: block !important; margin-bottom: 4px !important; }
.vm { font-size: 12px; margin-bottom: 10px; }
.body { white-space: pre-wrap; line-height: 1.6; background: #f8fafc; border: 1px solid var(--line2); border-radius: 8px; padding: 10px 12px; }
.answer { margin-top: 12px; border-left: 3px solid var(--ok); padding-left: 10px; }
.answer .body { background: #f0fdf4; border-color: #dcfce7; }
.ah { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; font-size: 12.5px; }
.wait { margin-top: 12px; font-size: 12.5px; }
.proc { margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--line); display: flex; flex-direction: column; gap: 8px; }
.proc h4 { margin: 0; font-size: 13px; }
.steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
.step { height: 30px; border: 1px solid var(--line); background: #fff; border-radius: 6px; font: inherit; font-size: 12.5px; cursor: pointer; color: var(--muted);
  transition: all var(--t-fast); }
.step:hover { border-color: #c5cede; color: var(--ink); }
.step.on { color: #fff; font-weight: 700; border-color: transparent; }
.step.on.OPEN { background: var(--pri); } .step.on.IN_PROGRESS { background: var(--warn); }
.step.on.DONE { background: var(--ok); } .step.on.REJECTED { background: var(--err); }
.emptyp { height: 100%; min-height: 200px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 2px; }
.emptyp p { margin: 0; }
@media (max-width: 1200px) { .split { grid-template-columns: 1fr; } }
</style>
