<template>
  <div class="ship-chat">
    <section v-if="open" id="ship-chat-panel" class="chat-panel" aria-labelledby="ship-chat-title" @keydown.esc="close">
      <header>
        <div><h2 id="ship-chat-title">조선소 챗봇</h2><small>로컬 AI</small></div>
        <button type="button" aria-label="챗봇 닫기" @click="close">×</button>
      </header>
      <div ref="transcript" class="messages" role="log" aria-label="대화">
        <p>안녕하세요! 아래 버튼을 누르고 보고 싶은 항목을 선택해 주세요. 질문을 직접 입력해도 돼요.</p>
        <div class="quick-actions" role="group" aria-label="빠른 조회">
          <button v-for="action in quickActions" :key="action.label" type="button" :disabled="pending || !!feedbackKind" @click="send(action.question)">
            {{ action.label }}
          </button>
          <button type="button" :disabled="pending || !!feedbackKind" @click="showManual()">매뉴얼</button>
          <button type="button" :disabled="pending || !!feedbackKind" @click="beginFeedback('suggestion')">건의하기</button>
          <button type="button" :disabled="pending || !!feedbackKind" @click="beginFeedback('inquiry')">문의하기</button>
          <button type="button" class="report-action" :disabled="pending || !!feedbackKind" @click="beginReport">📄 보고서 작성하기</button>
        </div>
        <div v-for="(message, index) in messages" :key="index">
          <p :class="message.role">{{ message.content }}</p>
          <ChatReport v-if="message.report" @update="scrollToEnd" />
          <div v-if="message.hulls?.length" class="hull-options">
            <button v-for="hull in message.hulls" :key="hull.hull_no" type="button" @click="openHull(hull.hull_no)">
              <strong>{{ hull.hull_no }} · {{ hull.hull_nm || '호선' }}</strong>
              <small>{{ codeName('HULLSTAT', hull.hull_status) || '상태 미등록' }} · {{ hull.progress == null ? '계획 없음' : hull.progress + '%' }}</small>
            </button>
          </div>
          <div v-if="message.choices?.length" class="hull-options">
            <button v-for="item in message.choices" :key="item.drawing_id ?? item.plan_id ?? item.hull_no"
              type="button" :disabled="pending" @click="choose(message.choiceType, item)">
              <strong>{{ item.label || (item.drawing_no ? item.drawing_no + ' · ' + item.drawing_nm : item.hull_no + ' · ' + (item.hull_nm || '호선')) }}</strong>
              <small v-if="item.drawing_no">{{ item.hull_no }} · {{ codeName('DWGSTAT', item.dwg_status) }}</small>
            </button>
          </div>
        </div>
        <p v-if="pending">답변을 작성 중입니다…</p>
        <p v-if="error" class="chat-error" role="alert">{{ error }}</p>
      </div>
      <p v-if="feedbackKind" class="feedback-mode">
        {{ feedbackKind === 'suggestion' ? '건의 접수' : '문의 접수' }}
        <button type="button" :disabled="pending" @click="feedbackKind = null">취소</button>
      </p>
      <form @submit.prevent="feedbackKind ? submitFeedback() : send()">
        <input ref="input" v-model="draft" aria-label="메시지" :placeholder="feedbackKind ? '접수할 내용 입력' : '메시지 입력'" maxlength="2000" autocomplete="off" />
        <button type="submit" :disabled="pending || !draft.trim()">{{ feedbackKind ? '접수' : '보내기' }}</button>
      </form>
    </section>
    <button v-if="!open" type="button" class="greeting" @click="toggle">
      안녕하세요! 친절한 조선소 AI 에이전트입니다.<br />
      눌러서 질문해 보세요.
    </button>
    <button ref="launcher" type="button" class="launcher" :aria-expanded="open" :aria-controls="open ? 'ship-chat-panel' : undefined"
      :aria-label="open ? '조선소 챗봇 닫기' : '조선소 챗봇 열기'" @click="toggle">
      <span class="mascot" aria-hidden="true">
        <span class="stack"></span><span class="bridge"></span>
        <span class="boat"><i></i><i></i><b></b></span>
      </span>
      <span class="wake" aria-hidden="true"></span>
    </button>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { api } from '../api/client.js'
import { codeName } from '../stores/session.js'
import ChatReport from './ChatReport.vue'

// 보고서 작성(명세 외 요청 기능): 범위·형식 선택 카드를 대화에 띄운다.
function beginReport() {
  error.value = ''
  messages.value.push({ role: 'user', content: '보고서 작성하기' },
    { role: 'assistant', content: '보고서 범위와 형식을 골라 주세요. 권한이 있는 호선·공정·도면 현황을 담아 만들어 드릴게요.', report: true })
  nextTick(scrollToEnd)
}

const emit = defineEmits(['open-hull', 'open-drawing', 'feedback-submitted', 'open-manual'])
function openHull(hullNo) {
  open.value = false
  emit('open-hull', hullNo)
}

const quickActions = [
  { label: '호선 정보', question: '호선 정보 알려줘' },
  { label: '도면 정보', question: '도면 정보 알려줘' },
  { label: '공정 실적', question: '공정 실적 알려줘' },
]

const open = ref(false)
const draft = ref('')
const feedbackKind = ref(null)
let feedbackRequest

async function beginFeedback(kind) {
  feedbackKind.value = kind
  feedbackRequest = null
  error.value = ''
  await nextTick()
  input.value?.focus()
}

async function submitFeedback() {
  const content = draft.value.trim()
  const kind = feedbackKind.value
  if (!content || !kind || pending.value) return
  if (feedbackRequest?.content !== content || feedbackRequest.kind !== kind) {
    feedbackRequest = { kind, content, request_id: crypto.randomUUID() }
  }
  pending.value = true
  error.value = ''
  try {
    const { receipt } = await api.post('/api/chat/feedback', feedbackRequest)
    messages.value.push({ role: 'user', content }, { role: 'assistant', content: `접수했습니다. 접수번호 ${receipt}` })
    if (draft.value.trim() === content) draft.value = ''
    feedbackKind.value = null
    feedbackRequest = null
    emit('feedback-submitted')
  } catch (err) {
    error.value = err.message
  } finally {
    pending.value = false
    nextTick(scrollToEnd)
  }
}
const pending = ref(false)
const error = ref('')
const messages = ref([])
const input = ref(null)
const launcher = ref(null)
const transcript = ref(null)

async function close() {
  open.value = false
  await nextTick()
  launcher.value?.focus()
}
async function toggle() {
  if (open.value) return close()
  open.value = true
  await nextTick()
  input.value?.focus()
  scrollToEnd()
}
function scrollToEnd() {
  if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight
}
async function choose(type, item) {
  if (type === 'drawing') {
    open.value = false
    emit('open-drawing', item.drawing_id)
    return
  }
  pending.value = true
  error.value = ''
  try {
    if (type === 'progress-hull') {
      const { plans } = await api.get(`/api/hulls/${encodeURIComponent(item.hull_no)}/progress-targets`, { include_done: true })
      messages.value.push({ role: 'assistant', content: plans.length ? `${item.hull_no}호선의 공정을 선택해 주세요.` : '등록된 공정이 없습니다.',
        choiceType: 'progress-plan', choices: plans })
    } else {
      const { plan, history } = await api.get(`/api/plans/${item.plan_id}/progress`)
      const latest = history[0]
      const detail = latest
        ? `최근 작업일 ${latest.work_dt} · 누적 ${latest.progress_rate}% · 공수 ${latest.man_hour ?? '미입력'} · 인원 ${latest.worker_cnt ?? '미입력'}`
        : '등록된 실적 이력이 없습니다.'
      messages.value.push({ role: 'assistant', content: `${plan.label}\n상태 ${codeName('PLANSTAT', plan.plan_status)} · 진척률 ${plan.progress_rate}%\n${detail}` })
    }
  } catch (err) {
    error.value = err.message
  } finally {
    pending.value = false
    nextTick(scrollToEnd)
  }
}
function showManual(section) {
  open.value = false
  emit('open-manual', section)
}
function manualTopic(question) {
  if (/결재/.test(question)) return 'dwg-approval'
  if (/도면/.test(question)) return 'dwg-list'
  if (/실적/.test(question)) return 'progress'
  if (/공정/.test(question)) return 'plan-gantt'
  if (/호선|3d|야드/i.test(question)) return 'hull-list'
  if (/건의|문의/.test(question)) return 'inquiry'
  return 'dashboard'
}
async function send(questionText) {
  const content = (questionText ?? draft.value).trim()
  if (!content || pending.value) return
  error.value = ''
  if (!questionText) draft.value = ''
  if (/매뉴얼|메뉴얼|사용법|사용\s*방법|업무\s*흐름|어떻게\s*(?:사용|쓰|보)/.test(content)) {
    showManual(manualTopic(content))
    return
  }
  pending.value = true
  const question = { role: 'user', content }
  const history = messages.value.slice(-10).map(message => ({ role: message.role, content: message.content.slice(0, 2000) }))
  messages.value.push(question)
  nextTick(scrollToEnd)
  try {
    const { answer, hulls, choices, choice_type: choiceType, feedback_kind: kind } = await api.post('/api/chat', { messages: [...history, question] })
    messages.value.push({ role: 'assistant', content: answer, hulls, choices, choiceType })
    if (kind) beginFeedback(kind)
  } catch (err) {
    messages.value.pop()
    if (!draft.value) draft.value = content
    error.value = err.message
  } finally {
    pending.value = false
    nextTick(scrollToEnd)
  }
}
</script>

<style scoped>
.ship-chat { position: fixed; bottom: max(14px, env(safe-area-inset-bottom)); left: 14px; z-index: 40; }
.greeting { position: absolute; left: 76px; bottom: 8px; width: max-content; max-width: min(240px, calc(100vw - 106px)); padding: 8px 11px; border: 1px solid #acdbe4; border-radius: 12px; background: #f0fafc; color: #18364d; box-shadow: 0 4px 12px #12395220; text-align: left; line-height: 1.5; font-size: 12px; cursor: pointer; }
@media (hover: hover) {
  .ship-chat:has(.greeting):hover .greeting { opacity: 0; }
}
.greeting::before { content: ''; position: absolute; left: -5px; bottom: 14px; width: 8px; height: 8px; transform: rotate(45deg); border-left: 1px solid #acdbe4; border-bottom: 1px solid #acdbe4; background: inherit; }
.launcher { position: relative; display: grid; place-items: center; width: 64px; height: 64px; border: 1px solid #acdbe4; border-radius: 22px; background: #def6fa; box-shadow: 0 4px 16px #12395240; cursor: pointer; }
.mascot { position: relative; display: block; width: 48px; height: 40px; animation: bob 2.6s ease-in-out infinite; }
.stack, .bridge, .boat, .wake { position: absolute; display: block; }
.stack { left: 17px; top: 5px; width: 8px; height: 10px; background: #ef8662; border-radius: 3px 3px 0 0; }
.bridge { left: 12px; top: 12px; width: 25px; height: 12px; background: #fdfcf5; border: 2px solid #285673; border-radius: 5px 5px 0 0; }
.bridge::after { content: ''; display: block; margin: 2px 4px; height: 4px; background: #85ccdc; border-radius: 2px; }
.boat { left: 2px; top: 21px; width: 44px; height: 17px; background: #275673; border-radius: 3px 4px 20px 16px; }
.boat i { position: absolute; top: 5px; left: 12px; width: 4px; height: 4px; border-radius: 50%; background: white; }
.boat i + i { left: 28px; }
.boat b { position: absolute; top: 8px; left: 19px; width: 7px; height: 5px; border-bottom: 2px solid white; border-radius: 50%; }
.wake { bottom: 9px; width: 35px; height: 4px; border-radius: 50%; background: #88ccdf; }
@keyframes bob { 0%, 100% { transform: translateY(-3px) rotate(-5deg); } 50% { transform: translateY(0) rotate(5deg); } }
@media (prefers-reduced-motion: reduce) { .mascot { animation: none; } }
.chat-panel { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; width: min(360px, calc(100vw - 28px)); height: min(440px, calc(100dvh - 102px)); margin-bottom: 10px; border-radius: 16px; border: 1px solid #ccdce7; overflow: hidden; box-shadow: 0 8px 28px #17364d40; background: #fff; color: #18364d; }
.chat-panel header { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: #173d58; color: #fff; }
.chat-panel h2 { margin: 0; font-size: 16px; }
.chat-panel header button { border: 0; background: transparent; color: #fff; font-size: 24px; cursor: pointer; }
.messages { overflow: auto; padding: 12px; }
.messages p { width: fit-content; max-width: 92%; margin: 0 0 8px; padding: 8px 10px; border-radius: 10px; background: #edf4f8; white-space: pre-wrap; overflow-wrap: anywhere; }
.messages .user { margin-left: auto; background: #d6eef4; }
.messages .chat-error { background: #fff0ed; color: #8c2e21; }
.quick-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.quick-actions button { border: 1px solid #a6cbd8; border-radius: 999px; padding: 5px 10px; background: #f0fafc; color: #18364d; cursor: pointer; }
.quick-actions button:disabled { opacity: .6; cursor: default; }
.quick-actions .report-action { background: #205471; border-color: #205471; color: #fff; font-weight: 600; }
.hull-options { display: grid; gap: 5px; margin: 0 0 10px; }
.hull-options button { display: grid; gap: 2px; text-align: left; padding: 8px; border: 1px solid #acdbe4; border-radius: 8px; background: #f0fafc; color: #18364d; cursor: pointer; overflow-wrap: anywhere; }
.hull-options button:hover { background: #d6eef4; }
.chat-panel:has(.feedback-mode) { grid-template-rows: auto minmax(0, 1fr) auto auto; }
.feedback-mode { display: flex; align-items: center; justify-content: space-between; margin: 0; padding: 4px 10px; background: #edf4f8; }
.feedback-mode button { cursor: pointer; }
.chat-panel form { display: flex; gap: 8px; padding: 10px; border-top: 1px solid #ccdce7; }
.chat-panel input { flex: 1; min-width: 0; border: 1px solid #adc1cf; border-radius: 8px; padding: 8px; font-size: 16px; }
.chat-panel form button { border: 0; border-radius: 8px; background: #205471; color: #fff; padding: 0 10px; cursor: pointer; }
.chat-panel form button:disabled { opacity: .5; cursor: default; }
</style>
