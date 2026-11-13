<template>
  <div v-if="ready" class="shell">
    <header class="hdr">
      <div class="brand">⚓ SWP 조선소 통합관리 <small>호선 / 공정 / 도면</small></div>
      <div class="grow"></div>
      <WeatherWidget />
      <div class="who">
        <b>{{ session.me.display_name }} 님</b>
        <small>{{ groupText }} · {{ session.me.today }}</small>
      </div>
      <div v-if="session.me.demo_role" class="demo-toggle" role="group" aria-label="데모 역할 전환">
        <button v-for="role in demoRoles" :key="role.id" type="button" class="hbtn"
          :aria-pressed="session.me.demo_role === role.id" :disabled="switching || session.me.demo_role === role.id"
          @click="switchDemo(role.id)">{{ role.label }}</button>
      </div>
      <button class="hbtn" type="button" @click="logout">로그아웃</button>
    </header>
    <div class="body">
      <nav class="menu">
        <div class="mtitle">MENU</div>
        <template v-for="m in roots" :key="m.menu_id">
          <div v-if="!m.token" class="mi grp" @click="toggle(m.menu_id)">
            <i>{{ collapsed[m.menu_id] ? '▶' : '▼' }}</i>{{ m.title }}
          </div>
          <div v-else class="mi" :class="{ on: activeToken === m.token }" @click="navigate(m.token)"><i>·</i>{{ m.title }}</div>
          <template v-if="!m.token && !collapsed[m.menu_id]">
            <div v-for="c in children(m.menu_id)" :key="c.menu_id" class="mi sub" :class="{ on: activeToken === c.token }" @click="navigate(c.token)">
              <i>·</i>{{ c.title }}
            </div>
          </template>
        </template>
      </nav>
      <main class="main">
        <div class="tabbar">
          <div v-for="t in tabs.state.tabs" :key="t.key" class="tab" :class="{ on: t.key === tabs.state.active }" @click="tabs.state.active = t.key">
            <span>{{ menuByToken(t.token)?.title || t.token }}</span>
            <button type="button" class="x" title="닫기" @click.stop="tabs.close(t.key)">×</button>
          </div>
          <div class="grow"></div>
          <button type="button" class="closeall" @click="openManual()">매뉴얼</button>
          <button v-if="tabs.state.tabs.length >= 2" type="button" class="closeall" @click="tabs.closeOthers()">다른 탭 닫기</button>
        </div>
        <div class="work">
          <div v-for="t in tabs.state.tabs" v-show="t.key === tabs.state.active" :key="t.key" class="screen">
            <component :is="screens[t.token] || PlaceholderScreen" :token="t.token" :param="t.param" :ctx="t.ctx" v-bind="t.token === 'hull-list' ? { active: t.key === tabs.state.active && !chatHull } : {}"
              :can-write="!!menuByToken(t.token)?.can_write" :title="menuByToken(t.token)?.title || ''" />
          </div>
        </div>
      </main>
    </div>
    <ShipChat @open-hull="chatHull = $event" @open-drawing="chatDrawing = $event" @feedback-submitted="refreshInquiryList" @open-manual="openManual" />
    <WorkflowManual v-if="manualSection" :section="manualSection" @close="manualSection = null" @navigate="openManualScreen" />
    <DrawingDetail v-if="chatDrawing" :drawing-id="chatDrawing" :can-write="false" @close="chatDrawing = null" />
    <HullDetail v-if="chatHull" :hull-no="chatHull" :can-write="!!menuByToken('hull-list')?.can_write"
      @close="chatHull = null" @changed="refreshHullList" />
  </div>
</template>

<script setup>
import { computed, onMounted, provide, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, tokenStore } from '../api/client.js'
import { clearSession, fail, loadSession, menuByToken, session, toast } from '../stores/session.js'
import { createTabs } from '../stores/tabs.js'
import DrawingDetail from '../screens/DrawingDetail.vue'
import HullDetail from '../screens/HullDetail.vue'
import WorkflowManual from '../components/WorkflowManual.vue'
import ShipChat from '../components/ShipChat.vue'
import WeatherWidget from '../components/WeatherWidget.vue'
import { screens, PlaceholderScreen } from '../screens/index.js'

const router = useRouter()
const ready = ref(false)
const chatHull = ref(null)
const chatDrawing = ref(null)
function refreshInquiryList() {
  for (const tab of tabs.state.tabs) {
    if (tab.token === 'inquiry') tab.ctx++
  }
}
function refreshHullList() {
  const tab = tabs.state.tabs.find(item => item.token === 'hull-list')
  if (tab) tab.ctx++
}
const collapsed = reactive({})

const tabs = createTabs({
  allowed: (token) => !!menuByToken(token),
  access: (token) => api.post('/api/me/menu-access', { menu_id: menuByToken(token).menu_id }),
  notify: toast,
})
const navigate = (token, param = null) => tabs.open(token, param)
provide('navigate', navigate)
const manualSection = ref(null)
function openManual(section) {
  manualSection.value = section || activeToken.value || 'dashboard'
}
function openManualScreen(token) {
  if (navigate(token)) manualSection.value = null
}
provide('openManual', openManual)

const roots = computed(() => session.menu.filter((m) => !m.parent_id).sort((a, b) => a.seq - b.seq))
const children = (id) => session.menu.filter((m) => m.parent_id === id).sort((a, b) => a.seq - b.seq)
const toggle = (id) => { collapsed[id] = !collapsed[id] }
const activeToken = computed(() => tabs.state.tabs.find((t) => t.key === tabs.state.active)?.token)
const groupText = computed(() => (session.me?.groups || []).map((g) => g.name).join(', ') || '-')

onMounted(async () => {
  try {
    await loadSession()
  } catch (e) {
    if (e.status !== 401) fail(e)
    return
  }
  ready.value = true
  const first = session.menu.find((m) => m.token)
  tabs.restore(menuByToken('dashboard') ? 'dashboard' : first?.token)
})

const demoRoles = [{ id: 'admin', label: '관리자' }, { id: 'user', label: '사용자' }]
const switching = ref(false)
async function switchDemo(role) {
  switching.value = true
  try {
    const result = await api.post('/api/auth/demo-role', { role })
    tokenStore.set(result.access_token)
    tabs.reset()
    window.location.reload()
  } catch (error) {
    fail(error)
    switching.value = false
  }
}

async function logout() {
  try { await api.post('/api/auth/logout') } catch { /* 결과와 무관하게 정리 */ }
  tokenStore.clear()
  tabs.reset()
  clearSession()
  router.replace('/login')
}
</script>

<style scoped>
.shell { height: 100%; display: flex; flex-direction: column; }
.hdr { height: 50px; flex: none; background: var(--navy); color: #fff; display: flex; align-items: center; gap: 14px; padding: 0 16px; }
.brand { font-size: 15px; font-weight: 700; white-space: nowrap; }
.brand small { font-size: 11px; font-weight: 400; opacity: .65; margin-left: 4px; }
.grow { flex: 1; }
.who { display: flex; flex-direction: column; line-height: 1.25; white-space: nowrap; }
.who small { font-size: 11px; opacity: .85; }
.hbtn { height: 26px; padding: 0 10px; border: 1px solid #3b5a8c; border-radius: 5px; background: transparent; color: #fff; font: inherit; cursor: pointer; }
.hbtn { transition: background var(--t-fast); }
.demo-toggle { display: flex; gap: 4px; }
.demo-toggle [aria-pressed="true"] { background: #fff; color: var(--navy); cursor: default; }
.hbtn:hover { background: var(--navy2); }
.body { flex: 1; display: flex; min-height: 0; }
.menu { width: 230px; flex: none; background: #fff; border-right: 1px solid var(--line); overflow: auto; padding-top: 10px; }
.mtitle { font-size: 11px; letter-spacing: 1px; color: var(--muted); padding: 4px 14px 8px; }
.mi { display: flex; align-items: center; gap: 6px; padding: 7px 14px; cursor: pointer; white-space: nowrap; margin: 1px 8px; border-radius: 7px;
  transition: background var(--t-fast), color var(--t-fast); }
.mi i { width: 12px; flex: none; font-style: normal; text-align: center; color: var(--muted); }
.mi.grp i { font-size: 9px; }
.mi.sub { padding-left: 26px; }
.mi:hover { background: #eef3fb; }
.mi.on { background: var(--sel); color: var(--pri-d); font-weight: 700; box-shadow: inset 3px 0 0 var(--pri); }
.mi.on i { color: var(--pri-d); }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.tabbar { height: 36px; flex: none; background: var(--tabs); padding: 6px 8px 0; display: flex; gap: 2px; align-items: flex-end; }
.tab { transition: background var(--t-fast), color var(--t-fast); height: 30px; display: flex; align-items: center; gap: 8px; padding: 0 8px 0 12px; border-radius: 6px 6px 0 0; background: var(--tab-off); font-size: 12.5px; cursor: pointer; white-space: nowrap; }
.tab.on { background: #fff; color: var(--navy); font-weight: 700; }
.x { width: 18px; height: 18px; border-radius: 50%; border: 0; background: transparent; color: var(--muted); cursor: pointer; font-size: 13px; line-height: 18px; padding: 0; }
.x:hover { background: var(--err); color: #fff; }
.closeall { align-self: center; margin-top: -6px; height: 24px; padding: 0 8px; border: 1px solid var(--line); border-radius: 5px; background: #fff; font: inherit; font-size: 12px; cursor: pointer; }
.work { flex: 1; min-height: 0; overflow: auto; padding: 14px 18px 24px; background: var(--bg); }
.screen { height: 100%; }
@media (max-width: 720px) {
  .menu { width: 160px; }
  .brand small { display: none; }
}
</style>
