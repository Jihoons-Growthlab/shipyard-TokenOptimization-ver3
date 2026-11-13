<template>
  <div class="um">
    <PageHead title="회원관리" desc="상단 목록 / 하단 입력·수정 (CRUD)" :readonly="!canWrite" />
    <form class="toolbar" @submit.prevent="load">
      <select v-model="f.status" class="ssel" aria-label="상태">
        <option value="">상태 전체</option>
        <option v-for="(v, k) in USER_STAT" :key="k" :value="k">{{ v[0] }}</option>
      </select>
      <input v-model.trim="f.q" class="fq" placeholder="아이디/이름/이메일/전화" />
      <button class="btn pri" type="submit">조회</button>
      <button class="btn" type="button" @click="resetFilter">초기화</button>
      <div class="grow"></div>
      <span class="cnt">{{ total }}명 · 승인대기 {{ pending }}명</span>
    </form>
    <div class="tw top">
      <table class="t user-table">
        <thead><tr><th>아이디</th><th>이름</th><th>이메일</th><th>전화번호</th><th>생년월일</th><th>상태</th><th>2차인증</th><th>권한그룹</th><th>가입일</th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.emp_no" class="click" :class="{ on: sel === u.emp_no }" @click="select(u)">
            <td><b>{{ u.emp_no }}</b></td><td>{{ u.display_name }}</td><td>{{ u.email }}</td><td>{{ u.phone }}</td><td>{{ u.birth_date }}</td>
            <td><span class="b" :class="USER_STAT[u.status]?.[1]">{{ USER_STAT[u.status]?.[0] || u.status }}</span></td>
            <td>{{ u.totp_enabled ? '사용' : '-' }}</td>
            <td>{{ u.groups.map(groupName).join(', ') || '-' }}</td>
            <td>{{ day(u.created_at) }}</td>
          </tr>
          <tr v-if="loaded && !users.length"><td colspan="9" class="empty">조회된 회원이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <section class="card bottom">
      <h3>{{ heading }}</h3>
      <form v-if="mode" class="uform" @submit.prevent="save">
        <div class="ubody">
        <div class="fg c4">
          <label class="f"><span>성 *</span><input v-model.trim="fm.last_name" name="last_name" /></label>
          <label class="f"><span>이름 *</span><input v-model.trim="fm.first_name" name="first_name" /></label>
          <label class="f"><span>생년월일 *</span><input v-model="fm.birth_date" name="birth_date" type="date" /></label>
          <label class="f"><span>전화번호 *</span><input v-model.trim="fm.phone" name="phone" placeholder="010-0000-0000" /></label>
          <label class="f s2"><span>이메일 *</span><input v-model.trim="fm.email" name="email" /></label>
          <label class="f"><span>아이디 *</span><input v-model.trim="fm.emp_no" name="emp_no" :readonly="mode === 'edit'" /></label>
          <label class="f"><span>{{ mode === 'edit' ? '비밀번호 (변경 시만 입력)' : '비밀번호 *' }}</span>
            <input v-model="fm.password" name="password" type="password" placeholder="8자 이상" autocomplete="new-password" />
          </label>
          <label class="f"><span>상태</span>
            <select v-model="fm.status" name="status"><option v-for="(v, k) in USER_STAT" :key="k" :value="k">{{ v[0] }}</option></select>
          </label>
          <label class="f"><span>권한 그룹</span>
            <select v-model="fm.group" name="group"><option value="">없음</option><option v-for="g in groups" :key="g.code" :value="g.code">{{ g.name }}</option></select>
          </label>
          <div class="f"><span>구글 2차인증</span><label class="chk"><input v-model="fm.totp_enabled" type="checkbox" name="totp_enabled" />사용 (등록된 사용자만)</label></div>
          <label class="f"><span>가입일</span><input :value="day(fm.created_at) || '-'" readonly /></label>
        </div>
        <div class="perm">
          <div class="phead">
            <b>메뉴 권한</b><span class="muted">회원별 지정이 그룹 권한보다 우선합니다.</span>
            <button v-if="mode === 'edit'" class="btn sm" type="button" :disabled="!perms.length" @click="resetPerms">그룹 기본값</button>
          </div>
          <p v-if="mode === 'new'" class="muted">저장한 뒤 메뉴 권한을 지정할 수 있습니다.</p>
          <div v-else class="pscroll">
          <table class="t ptable">
            <thead><tr><th>메뉴</th><th>없음</th><th>읽기</th><th>쓰기</th><th>그룹</th></tr></thead>
            <tbody>
              <tr v-for="m in perms" :key="m.menu_id" :class="{ ov: isOverride(m) }">
                <td :class="{ sub: m.parent_id }">{{ m.title }}<span v-if="isOverride(m)" class="b b-info">개별</span></td>
                <td v-for="v in [0, 1, 2]" :key="v" class="rc">
                  <input type="radio" :name="'perm-' + m.menu_id" :aria-label="`${m.title} ${LV[v]}`" :checked="eff(m) === v" @change="setLevel(m, v)" />
                </td>
                <td class="muted">{{ LV[m.group_level] }}</td>
              </tr>
            </tbody>
          </table>
          </div>
        </div>
        </div>
        <div class="bar-row">
          <button class="btn" type="button" @click="startNew">신규</button>
          <button class="btn pri" type="submit" :disabled="busy">저장</button>
          <button class="btn danger" type="button" :disabled="busy || mode !== 'edit'" @click="remove">삭제</button>
          <button v-if="mode === 'edit' && current?.status === 'pending'" class="btn ok" type="button" :disabled="busy" @click="approve">가입 승인</button>
        </div>
      </form>
      <template v-else>
        <p class="muted">목록에서 회원을 선택하거나 [신규]를 누르세요.</p>
        <div class="bar-row"><button class="btn" type="button" @click="startNew">신규</button></div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import { fail, loadSession, session, toast } from '../stores/session.js'
import PageHead from '../components/PageHead.vue'

defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const USER_STAT = { pending: ['승인대기', 'b-warn'], approved: ['승인', 'b-ok'], rejected: ['반려', 'b-bad'], disabled: ['중지', ''] }
const SELF_DELETE = '로그인 중인 본인 계정은 삭제할 수 없습니다.'

const f = reactive({ status: '', q: '' })
const users = ref([])
const total = ref(0)
const pending = ref(0)
const groups = ref([])
const loaded = ref(false)
const busy = ref(false)
const sel = ref(null)
const mode = ref('') // '' | 'new' | 'edit'
const fm = reactive({})

// 메뉴 권한: choice가 null이면 그룹 권한을 따른다. 0 없음 / 1 읽기 / 2 쓰기.
const LV = ['없음', '읽기', '쓰기']
const perms = ref([])
const eff = (m) => m.choice ?? m.group_level
const isOverride = (m) => m.choice !== null && m.choice !== m.group_level
const permsDirty = computed(() => perms.value.some((m) => m.choice !== m.user_level))

async function loadPerms(empNo) {
  perms.value = []
  try {
    const r = await api.get(`/api/users/${empNo}/menus`)
    if (sel.value === empNo) perms.value = r.menus.map((m) => ({ ...m, choice: m.user_level }))
  } catch (e) { fail(e) }
}
// 부모 메뉴가 없음이면 하위 메뉴가 보이지 않으므로, 하위를 열면 부모를 읽기로, 부모를 닫으면 하위도 닫는다.
function setLevel(m, v) {
  m.choice = v
  const parent = perms.value.find((x) => x.menu_id === m.parent_id)
  if (v > 0 && parent && eff(parent) === 0) parent.choice = 1
  if (v === 0) for (const c of perms.value) if (c.parent_id === m.menu_id) c.choice = 0
}
function resetPerms() {
  for (const m of perms.value) m.choice = null
}

const current = computed(() => users.value.find((u) => u.emp_no === sel.value) || null)
const heading = computed(() => (mode.value === 'edit' ? `회원 수정 — ${current.value?.display_name || fm.emp_no}` : mode.value === 'new' ? '회원 등록' : '입력 / 수정'))
// 사용자 응답의 groups는 [{code,name}]
const groupCode = (g) => (typeof g === 'object' && g ? g.code : g)
const groupName = (g) => (typeof g === 'object' && g ? g.name : groups.value.find((x) => x.code === g)?.name || g)
const day = (v) => (v ? String(v).slice(0, 10) : '')

async function load() {
  try {
    const r = await api.get('/api/users', { ...f })
    users.value = r.users
    total.value = r.total
    pending.value = r.pending
    loaded.value = true
  } catch (e) { fail(e) }
}
function resetFilter() {
  Object.assign(f, { status: '', q: '' })
  load()
}
function fill(u) {
  Object.assign(fm, {
    last_name: u?.last_name || '', first_name: u?.first_name || '', birth_date: u?.birth_date || '', phone: u?.phone || '',
    email: u?.email || '', emp_no: u?.emp_no || '', password: '', status: u?.status || 'approved',
    group: groupCode(u?.groups?.[0]) || '', totp_enabled: !!u?.totp_enabled, created_at: u?.created_at || '',
  })
}
function select(u) {
  sel.value = u.emp_no
  mode.value = 'edit'
  fill(u)
  loadPerms(u.emp_no)
}
function startNew() {
  sel.value = null
  mode.value = 'new'
  fill(null)
}
async function save() {
  const isNew = mode.value === 'new'
  const { password, group, created_at: _c, ...rest } = fm
  const body = { ...rest, groups: group ? [group] : [] }
  if (isNew || password) Object.assign(body, { password, password_confirm: password })
  busy.value = true
  try {
    const u = isNew ? await api.post('/api/users', body) : await api.patch(`/api/users/${fm.emp_no}`, body)
    if (!isNew && permsDirty.value) {
      await api.put(`/api/users/${u.emp_no}/menus`, { menus: perms.value.map((m) => ({ menu_id: m.menu_id, level: m.choice })) })
    }
    toast('저장되었습니다.', 'success')
    await load()
    select(u)
    if (u.emp_no === session.me?.emp_no) await loadSession()
  } catch (e) { fail(e) } finally { busy.value = false }
}
async function remove() {
  if (fm.emp_no === session.me?.emp_no) return toast(SELF_DELETE, 'error')
  if (!window.confirm(`회원 ${fm.emp_no} 을(를) 삭제합니다.`)) return
  busy.value = true
  try {
    await api.del(`/api/users/${fm.emp_no}`)
    toast('삭제되었습니다.', 'success')
    sel.value = null
    mode.value = ''
    await load()
  } catch (e) { fail(e) } finally { busy.value = false }
}
async function approve() {
  const u = current.value
  busy.value = true
  try {
    await api.post(`/api/users/${u.emp_no}/approve`, { groups: fm.group ? [fm.group] : [] })
    toast(`${u.display_name} 님의 가입을 승인했습니다.`, 'success')
    await load()
    if (current.value) select(current.value)
  } catch (e) { fail(e) } finally { busy.value = false }
}

onMounted(async () => {
  await load()
  try { groups.value = await api.get('/api/auth-groups') } catch (e) { fail(e) }
})
</script>

<style scoped>
.um { height: 100%; display: flex; flex-direction: column; }
.ssel { width: 110px; }
.fq { width: 148px; }
.cnt { font-size: 12px; color: var(--muted); }
.top { flex: 1; min-height: 0; }
/* 아래 카드는 화면 높이에 맞추고, 메뉴 권한 표만 스크롤한다. 버튼 줄은 항상 보인다. */
.bottom { flex: 1; min-height: 0; overflow: auto; margin: 10px 0 0; display: flex; flex-direction: column; }
.bottom > h3 { flex: none; }
.uform { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.uform > .bar-row { flex: none; margin-top: 10px; }
.ubody { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) 400px; gap: 16px; align-items: start; }
.perm { min-width: 0; height: 100%; min-height: 0; display: flex; flex-direction: column; }
.phead { flex: none; }
.pscroll { flex: 1; min-height: 90px; overflow: auto; border: 1px solid #e2e7ef; border-radius: 8px; }
.pscroll .ptable th { box-shadow: 0 1px 0 var(--line); }
.phead { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12.5px; }
.phead .btn { margin-left: auto; }
.ptable th, .ptable td { padding: 3px 8px; }
.ptable .rc { text-align: center; width: 44px; }
.ptable th:nth-child(n+2) { text-align: center; }
.ptable .sub { padding-left: 22px; }
.ptable tr.ov td:first-child { font-weight: 600; }
.ptable .b { margin-left: 6px; }
@media (max-width: 1200px) {
  .ubody { grid-template-columns: minmax(0, 1fr); flex: none; }
  .perm { height: auto; }
  .pscroll { max-height: 240px; }
}
</style>
