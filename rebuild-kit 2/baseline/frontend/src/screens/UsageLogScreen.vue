<template>
  <div class="ul">
    <PageHead title="사용 로그" desc="누가 어떤 기능을 얼마나 썼는지 API 호출·메뉴 진입 기록으로 봅니다. (관리자 전용)" />
    <div class="toolbar">
      <select v-model.number="days" class="psel" aria-label="기간" @change="load">
        <option :value="7">최근 7일</option><option :value="30">최근 30일</option><option :value="90">최근 90일</option>
      </select>
      <select v-model="empNo" class="usel" aria-label="사용자" @change="load">
        <option value="">사용자 전체</option>
        <option v-for="u in s?.user_options || []" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option>
      </select>
      <button class="btn" type="button" @click="load">새로고침</button>
      <button v-if="empNo" class="btn" type="button" @click="setUser('')">필터 해제</button>
      <div class="grow"></div>
      <span v-if="s?.demo_calls" class="b b-warn" title="init-db --demo-usage로 만든 예시 로그가 포함되어 있습니다.">예시 데이터 {{ s.demo_calls.toLocaleString() }}건 포함</span>
    </div>

    <p v-if="!s" class="muted">불러오는 중…</p>
    <template v-else>
      <div class="kpis">
        <div v-for="k in kpis" :key="k.label" class="card kpi" :class="k.cls">
          <span>{{ k.label }}</span><b>{{ k.value }}</b><small class="muted">{{ k.sub }}</small>
        </div>
      </div>

      <div class="g21">
        <section class="card">
          <h3>일별 호출 추이 <span class="muted lg"><i class="dot pri"></i>호출 <i class="dot err"></i>오류</span></h3>
          <div class="chart" @mouseleave="hi = -1">
            <svg :viewBox="`0 0 ${CW} ${CH}`" class="line" preserveAspectRatio="none">
              <defs>
                <linearGradient id="ul-area" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0" stop-color="#2563eb" stop-opacity=".28" /><stop offset="1" stop-color="#2563eb" stop-opacity="0" />
                </linearGradient>
              </defs>
              <line v-for="t in yTicks" :key="t.v" :x1="0" :x2="CW" :y1="t.y" :y2="t.y" class="grid" />
              <rect v-for="(d, i) in s.daily" :key="'e' + d.date" :x="xs(i) - barW / 2" :y="ys(d.errors)" :width="barW" :height="CH - PADB - ys(d.errors)" class="ebar" />
              <path :d="area" fill="url(#ul-area)" class="area" />
              <path :d="line" class="stroke" pathLength="1" />
              <line v-if="hi >= 0" :x1="xs(hi)" :x2="xs(hi)" y1="0" :y2="CH - PADB" class="guide" />
              <circle v-if="hi >= 0" :cx="xs(hi)" :cy="ys(s.daily[hi].calls)" r="4" class="pt" />
              <rect v-for="(d, i) in s.daily" :key="'h' + d.date" :x="xs(i) - step / 2" y="0" :width="step" :height="CH" fill="transparent" @mouseenter="hi = i" />
            </svg>
            <div class="yl"><span v-for="t in yTicks" :key="t.v" :style="{ top: (t.y / CH) * 100 + '%' }">{{ t.v }}</span></div>
            <div class="xl"><span v-for="l in xLabels" :key="l.i" :style="{ left: (xs(l.i) / CW) * 100 + '%' }">{{ l.t }}</span></div>
            <div v-if="hi >= 0" class="tip" :style="{ left: (xs(hi) / CW) * 100 + '%' }">
              <b>{{ s.daily[hi].date }}</b><br />호출 {{ s.daily[hi].calls }} · 오류 {{ s.daily[hi].errors }} · 사용자 {{ s.daily[hi].users }}
            </div>
          </div>
        </section>
        <section class="card">
          <h3>시간대별 호출 <span class="muted lg">(한국 시간)</span></h3>
          <div class="hours">
            <div v-for="(n, h) in s.hours" :key="h" class="hc" :title="`${h}시 · ${n}건`">
              <i :style="{ height: (n / maxHour) * 100 + '%', animationDelay: h * 15 + 'ms' }" :class="{ peak: n === maxHour && n }"></i>
              <span>{{ h % 3 === 0 ? h : '' }}</span>
            </div>
          </div>
        </section>
      </div>

      <div class="g3">
        <section class="card">
          <h3>기능별 사용</h3>
          <div v-for="(f, i) in s.features.slice(0, 10)" :key="f.feature" class="hb">
            <span class="ell">{{ f.feature }}</span>
            <div class="bar"><i :style="{ width: pctOf(f.calls, s.features[0]?.calls) + '%', background: PALETTE[i % PALETTE.length], animationDelay: i * 40 + 'ms' }"></i></div>
            <b>{{ f.calls.toLocaleString() }}</b>
          </div>
          <p v-if="!s.features.length" class="none">기록이 없습니다.</p>
        </section>
        <section class="card">
          <h3>사용자별 호출 TOP 10 <span class="muted lg">클릭하면 그 사용자만 봅니다</span></h3>
          <div v-for="(u, i) in s.top_users" :key="u.emp_no" class="hb click" :class="{ on: u.emp_no === empNo }" @click="setUser(u.emp_no === empNo ? '' : u.emp_no)">
            <span class="ell" :title="`${u.display_name || u.emp_no} · 주 사용: ${u.top_feature || '-'} · 최근 ${fmtUtc(u.last_dt)}`">
              {{ u.display_name || u.emp_no }} <small class="muted">{{ u.top_feature }}</small>
            </span>
            <div class="bar"><i :style="{ width: pctOf(u.calls, s.top_users[0]?.calls) + '%', animationDelay: i * 40 + 'ms' }"></i></div>
            <b>{{ u.calls.toLocaleString() }}</b>
          </div>
          <p v-if="!s.top_users.length" class="none">기록이 없습니다.</p>
        </section>
        <section class="card">
          <h3>메뉴 진입 <span class="muted lg">화면을 연 횟수</span></h3>
          <div v-for="(m, i) in s.menus" :key="m.menu_id" class="hb">
            <span class="ell">{{ m.title }}</span>
            <div class="bar"><i class="alt" :style="{ width: pctOf(m.opens, s.menus[0]?.opens) + '%', animationDelay: i * 40 + 'ms' }"></i></div>
            <b>{{ m.opens }}<small class="muted"> / {{ m.users }}명</small></b>
          </div>
          <p v-if="!s.menus.length" class="none">기록이 없습니다.</p>
        </section>
      </div>

      <div class="g21">
        <section class="card">
          <h3>많이 호출된 API TOP 15</h3>
          <div class="tw">
            <table class="t">
              <thead><tr><th>기능</th><th>요청</th><th class="num">호출</th><th class="num">오류</th><th class="num">평균 ms</th><th class="num">최대 ms</th></tr></thead>
              <tbody>
                <tr v-for="e in s.endpoints" :key="e.method + e.path">
                  <td>{{ e.feature }}</td>
                  <td><span class="m" :class="e.method">{{ e.method }}</span> <code>{{ e.path }}</code></td>
                  <td class="num"><b>{{ e.calls.toLocaleString() }}</b></td>
                  <td class="num" :class="{ err: e.errors }">{{ e.errors || '-' }}</td>
                  <td class="num">{{ e.avg_ms }}</td>
                  <td class="num muted">{{ e.max_ms }}</td>
                </tr>
                <tr v-if="!s.endpoints.length"><td colspan="6" class="empty">기록이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="card">
          <h3>최근 오류</h3>
          <div v-for="e in s.recent_errors" :key="e.call_dt + e.path" class="err-row">
            <span class="b" :class="e.status >= 500 ? 'b-bad' : 'b-warn'">{{ e.status }}</span>
            <div class="ell"><code>{{ e.method }} {{ e.path }}</code><br /><small class="muted">{{ e.display_name || e.emp_no || '비로그인' }} · {{ fmtUtc(e.call_dt) }}</small></div>
          </div>
          <p v-if="!s.recent_errors.length" class="none">오류가 없습니다.</p>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client.js'
import { fail } from '../stores/session.js'
import { fmtUtc } from '../utils/date.js'
import PageHead from '../components/PageHead.vue'

defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const PALETTE = ['#2563eb', '#0ea5e9', '#16a34a', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#64748b', '#ef4444', '#84cc16']
const CW = 640
const CH = 200
const PADB = 4
const days = ref(7)
const empNo = ref('')
const s = ref(null)
const hi = ref(-1)

async function load() {
  try {
    s.value = await api.get('/api/usage/summary', { days: days.value, emp_no: empNo.value || undefined })
    hi.value = -1
  } catch (e) { fail(e) }
}
function setUser(v) {
  empNo.value = v
  load()
}

const pctOf = (v, max) => (max ? Math.max(2, (v / max) * 100) : 0)
const kpis = computed(() => {
  const k = s.value.kpi
  return [
    { label: 'API 호출', value: k.calls.toLocaleString(), sub: `최근 ${s.value.days}일` },
    { label: '사용자', value: k.users, sub: '호출한 회원 수' },
    { label: '로그인', value: k.logins, sub: '로그인 횟수' },
    { label: '오류율', value: `${k.error_rate}%`, sub: `오류 ${k.errors}건 (4xx·5xx)`, cls: k.error_rate >= 5 ? 'bad' : '' },
    { label: '평균 응답', value: `${k.avg_ms}ms`, sub: '서버 처리 시간', cls: k.avg_ms >= 500 ? 'bad' : '' },
  ]
})

// 일별 추이 차트 좌표
const maxCalls = computed(() => Math.max(5, ...s.value.daily.map((d) => d.calls)))
const niceMax = computed(() => {
  const m = maxCalls.value
  const p = 10 ** Math.floor(Math.log10(m))
  return Math.ceil(m / p) * p
})
const step = computed(() => CW / Math.max(1, s.value.daily.length))
const barW = computed(() => Math.max(2, Math.min(14, step.value * 0.5)))
const xs = (i) => step.value * (i + 0.5)
const ys = (v) => (CH - PADB) - (v / niceMax.value) * (CH - PADB - 10)
const line = computed(() => s.value.daily.map((d, i) => `${i ? 'L' : 'M'}${xs(i).toFixed(1)} ${ys(d.calls).toFixed(1)}`).join(''))
const area = computed(() => `${line.value}L${xs(s.value.daily.length - 1).toFixed(1)} ${CH - PADB}L${xs(0).toFixed(1)} ${CH - PADB}Z`)
const yTicks = computed(() => [0, 0.5, 1].map((r) => ({ v: Math.round(niceMax.value * r), y: ys(niceMax.value * r) })))
const xLabels = computed(() => {
  const n = s.value.daily.length
  const every = n <= 7 ? 1 : n <= 30 ? 5 : 15
  return s.value.daily.map((d, i) => ({ i, t: d.date.slice(5) })).filter((l) => (n - 1 - l.i) % every === 0)
})
const maxHour = computed(() => Math.max(1, ...s.value.hours))

onMounted(load)
</script>

<style scoped>
.ul { padding-bottom: 8px; }
.psel { width: 120px; }
.usel { width: 180px; }
.kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.kpi { margin: 0; display: flex; flex-direction: column; gap: 1px; position: relative; overflow: hidden; animation: rise-in .4s var(--ease) both; }
.kpi::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--pri); opacity: .7; }
.kpi.bad::before { background: var(--err); }
.kpi span { font-size: 12px; color: var(--muted); }
.kpi b { font-size: 24px; line-height: 1.25; }
.kpi.bad b { color: var(--err); }
.kpi small { font-size: 11px; }
.g21 { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 12px; margin-bottom: 12px; }
.g3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.g21 .card, .g3 .card { margin: 0; min-width: 0; }
.lg { font-size: 11.5px; font-weight: 400; display: inline-flex; align-items: center; gap: 4px; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-left: 6px; }
.dot.pri { background: var(--pri); } .dot.err { background: #f87171; }
.chart { position: relative; height: 210px; margin: 4px 0 18px 30px; }
.line { width: 100%; height: 200px; display: block; overflow: visible; }
.grid { stroke: var(--line2); stroke-width: 1; vector-effect: non-scaling-stroke; }
.area { animation: fade-in .8s var(--ease) both; }
.stroke { fill: none; stroke: var(--pri); stroke-width: 2.2; vector-effect: non-scaling-stroke; stroke-linejoin: round; stroke-linecap: round;
  stroke-dasharray: 1; stroke-dashoffset: 0; animation: draw 1s var(--ease) both; }
@keyframes draw { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
.ebar { fill: #fca5a5; }
.guide { stroke: #94a3b8; stroke-dasharray: 3 3; vector-effect: non-scaling-stroke; }
.pt { fill: #fff; stroke: var(--pri); stroke-width: 2; vector-effect: non-scaling-stroke; }
.yl span { position: absolute; left: -30px; width: 26px; text-align: right; transform: translateY(-50%); font-size: 10px; color: var(--muted); }
.xl span { position: absolute; bottom: -16px; transform: translateX(-50%); font-size: 10px; color: var(--muted); white-space: nowrap; }
.tip { position: absolute; top: 4px; transform: translateX(-50%); background: #1e293b; color: #fff; font-size: 11px; padding: 5px 9px; border-radius: 6px;
  white-space: nowrap; pointer-events: none; box-shadow: var(--shadow-md); z-index: 2; }
.hours { height: 210px; display: flex; align-items: stretch; gap: 3px; padding-top: 6px; }
.hc { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 4px; min-width: 0; }
.hc i { display: block; width: 100%; min-height: 2px; border-radius: 4px 4px 1px 1px; background: linear-gradient(180deg, #93c5fd, #3b82f6);
  transform-origin: bottom; animation: grow-y .6s var(--ease) both; transition: filter var(--t-fast); }
.hc i.peak { background: linear-gradient(180deg, #60a5fa, var(--pri-d)); }
.hc:hover i { filter: brightness(1.12); }
.hc span { font-size: 10px; color: var(--muted); height: 12px; }
.hb { display: grid; grid-template-columns: 118px 1fr 64px; gap: 8px; align-items: center; padding: 4px 6px; margin: 0 -6px; border-radius: 6px; transition: background var(--t-fast); }
.hb.click { cursor: pointer; }
.hb.click:hover, .hb.on { background: var(--hover); }
.hb.on { box-shadow: inset 3px 0 0 var(--pri); }
.hb > b { text-align: right; font-size: 12px; }
.hb small { font-size: 10.5px; font-weight: 400; }
.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar { height: 10px; border-radius: 5px; background: #eef1f6; overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #60a5fa, var(--pri)); transform-origin: left; animation: grow-x .7s var(--ease) both; }
.bar i.alt { background: linear-gradient(90deg, #5eead4, #0d9488); }
.none { color: var(--muted); text-align: center; margin: 18px 0; }
.tw { max-height: 330px; }
code { font: 11.5px ui-monospace, SFMono-Regular, Menlo, monospace; color: #334155; }
.m { display: inline-block; min-width: 46px; text-align: center; font-size: 10px; font-weight: 700; border-radius: 4px; padding: 1px 4px; }
.m.GET { background: #e0f2fe; color: #0369a1; } .m.POST { background: #dcfce7; color: #15803d; }
.m.PATCH, .m.PUT { background: #fef3c7; color: #92400e; } .m.DELETE { background: #fee2e2; color: #b91c1c; }
td.err { color: var(--err); font-weight: 600; }
.err-row { display: grid; grid-template-columns: 44px 1fr; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--line2); }
.err-row:last-of-type { border-bottom: 0; }
@media (max-width: 1200px) {
  .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .g21, .g3 { grid-template-columns: 1fr; }
}
</style>
