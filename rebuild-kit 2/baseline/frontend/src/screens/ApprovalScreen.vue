<template>
  <div>
    <PageHead title="도면 결재함" :desc="`${session.me?.display_name || ''} 님의 결재 대기와 배포 대기 도면입니다.`" :readonly="!canWrite" />
    <section class="card">
      <h3>내 결재 대기 <span class="b b-warn">{{ inbox.waiting.length }}</span></h3>
      <div class="tw">
        <table class="t apv-wait">
          <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>단계</th><th>변경사유</th><th>의견</th><th></th></tr></thead>
          <tbody>
            <tr v-for="w in inbox.waiting" :key="w.approval_id">
              <td><a class="lnk" href="#" @click.prevent="dwgId = w.drawing_id">{{ w.drawing_no }}</a></td>
              <td>{{ w.drawing_nm }}</td>
              <td>Rev{{ w.rev_no }}</td>
              <td>{{ STEP_NM[w.step_no] }}</td>
              <td class="wrap">{{ w.change_desc }}</td>
              <td><input v-model.trim="comments[w.approval_id]" class="cmt" name="comment" placeholder="의견 (반려 시 필수)" /></td>
              <td class="acts">
                <template v-if="canWrite">
                  <button class="btn ok sm" type="button" :disabled="busy" @click="decide(w, 'APPROVE')">승인</button>
                  <button class="btn danger sm" type="button" :disabled="busy" @click="decide(w, 'REJECT')">반려</button>
                </template>
              </td>
            </tr>
            <tr v-if="loaded && !inbox.waiting.length"><td colspan="7" class="empty">결재 대기 건이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h3>배포 대기 (승인 완료) <span class="b b-info">{{ inbox.ready.length }}</span></h3>
      <div class="tw">
        <table class="t apv-ready">
          <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>배포 시 착수 가능해질 수 있는 공정</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in inbox.ready" :key="r.drawing_id">
              <td><a class="lnk" href="#" @click.prevent="dwgId = r.drawing_id">{{ r.drawing_no }}</a></td>
              <td>{{ r.drawing_nm }}</td>
              <td>Rev{{ r.rev_no }}</td>
              <td class="wrap">{{ r.effect_plans.length ? r.effect_plans.join(', ') : '-' }}</td>
              <td class="acts"><button v-if="inbox.can_issue" class="btn ok sm" type="button" :disabled="busy" @click="issue(r)">배포</button></td>
            </tr>
            <tr v-if="loaded && !inbox.ready.length"><td colspan="5" class="empty">배포 대기 도면이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h3>최근 결재 이력</h3>
      <div class="tw">
        <table class="t apv-hist">
          <thead><tr><th>일시</th><th>도면번호</th><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th><th>의견</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.approval_id">
              <td>{{ h.act_dt }}</td><td>{{ h.drawing_no }}</td><td>Rev{{ h.rev_no }}</td><td>{{ STEP_NM[h.step_no] }}</td>
              <td>{{ h.approver_nm || '-' }}</td>
              <td><span class="b" :class="RESULT_BADGE[h.result]?.[1]">{{ RESULT_BADGE[h.result]?.[0] || h.result }}</span></td>
              <td class="wrap">{{ h.comment }}</td>
            </tr>
            <tr v-if="loaded && !history.length"><td colspan="7" class="empty">결재 이력이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <DrawingDetail v-if="dwgId" :key="dwgId" :drawing-id="dwgId" :can-write="!!menuByToken('dwg-list')?.can_write" @close="dwgId = null" @changed="load" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api/client.js'
import { fail, menuByToken, session, toast } from '../stores/session.js'
import { RESULT_BADGE, STEP_NM } from '../utils/drawing.js'
import PageHead from '../components/PageHead.vue'
import DrawingDetail from './DrawingDetail.vue'

defineProps({ token: String, param: [String, Number], ctx: Number, canWrite: Boolean, title: String })

const inbox = reactive({ waiting: [], ready: [], can_issue: false })
const history = ref([])
const comments = reactive({})
const loaded = ref(false)
const busy = ref(false)
const dwgId = ref(null)

async function load() {
  try {
    const [i, h] = await Promise.all([api.get('/api/approvals/inbox'), api.get('/api/approvals/history')])
    Object.assign(inbox, i)
    history.value = h
    loaded.value = true
  } catch (e) { fail(e) }
}
/** 처리 중 버튼 비활성, 성공·실패와 관계없이 다시 불러온다. */
async function act(fn, msg) {
  busy.value = true
  try {
    await fn()
    toast(msg, 'success')
  } catch (e) { fail(e) } finally {
    busy.value = false
    await load()
  }
}
function decide(w, result) {
  const comment = comments[w.approval_id] || ''
  if (result === 'REJECT' && !comment) return toast('반려 시 의견을 입력하세요.', 'error')
  return act(async () => {
    await api.post(`/api/approvals/${w.approval_id}/decision`, { result, comment })
    delete comments[w.approval_id]
  }, result === 'APPROVE' ? '승인했습니다.' : '반려했습니다. 도면은 작성중으로 되돌려집니다.')
}
const issue = (r) => act(() => api.post(`/api/drawings/${r.drawing_id}/revisions/${r.rev_no}/issue`), '도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')

onMounted(load)
</script>

<style scoped>
.cmt { width: 148px; }
.acts { text-align: right; width: 1%; }
.acts .btn + .btn { margin-left: 4px; }
</style>
