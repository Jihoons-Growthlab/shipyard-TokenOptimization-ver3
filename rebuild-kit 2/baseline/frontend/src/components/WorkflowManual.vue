<template>
  <AppModal title="조선소 업무 매뉴얼" size="xl" @close="$emit('close')">
    <p class="manual-intro">업무 단계를 선택하면 실제 화면과 사용 순서를 볼 수 있습니다.</p>
    <nav class="manual-nav" aria-label="매뉴얼 목차">
      <button v-for="entry in visible" :key="entry.id" type="button" class="btn"
        :class="{ pri: current?.id === entry.id }" :aria-pressed="current?.id === entry.id"
        @click="selected = entry.id">{{ entry.title }}</button>
    </nav>
    <article v-if="current" class="manual-step">
      <div class="manual-head">
        <h2>{{ current.title }}</h2>
        <button v-if="current.token" type="button" class="btn" @click="$emit('navigate', current.token)">업무 화면 열기</button>
      </div>
      <ol>
        <li v-for="instruction in current.instructions" :key="instruction">{{ instruction }}</li>
      </ol>
      <figure v-if="images[current.id]">
        <img :src="images[current.id]" :alt="current.title + ' 예시 화면'" />
        <figcaption>화면 예시 · 계정 권한과 등록 데이터에 따라 다르게 표시될 수 있습니다.</figcaption>
      </figure>
    </article>
  </AppModal>
</template>

<script setup>
import { computed, ref } from 'vue'
import AppModal from './AppModal.vue'
import { menuByToken } from '../stores/session.js'

const props = defineProps({ section: String })
defineEmits(['close', 'navigate'])

const images = Object.fromEntries(Object.entries(import.meta.glob('../assets/manual/*.jpg', {
  eager: true, import: 'default',
})).map(([path, url]) => [path.split('/').pop().replace('.jpg', ''), url]))

const steps = [
  { id: 'dashboard', token: 'dashboard', title: '대시보드', instructions: [
    '호선·공정·도면 지표에서 전체 현황과 지연 항목을 확인합니다.',
    '호선별 진척률을 클릭해 해당 호선의 공정계획을 엽니다.',
    '호선 확인 → 공정계획 → 공정 실적 순서로 진행합니다. 도면은 작성 → 결재 → 배포 순서로 처리합니다.',
  ] },
  { id: 'hull-list', token: 'hull-list', title: '호선·3D 조선소', instructions: [
    '호선 목록에서 번호·이름으로 검색하거나 상태로 범위를 좁힙니다.',
    '표의 상세 버튼을 누르면 기본정보, 주요일정, 블록 구성과 연계 현황을 확인할 수 있습니다.',
    '목록 아래 3D 야드에서 선체에 마우스를 올리면 요약이 표시됩니다. 선체를 누르면 상세가 열리고 휠로 확대·축소할 수 있습니다.',
  ] },
  { id: 'plan-gantt', token: 'plan-gantt', title: '공정계획', instructions: [
    '호선을 선택하고 간트 차트에서 공정의 기간, 순서, 지연을 확인합니다.',
    '공정에 마우스를 올려 요약을 보고, 편집 권한이 있으면 막대를 드래그하거나 상세에서 일정을 조정합니다.',
  ] },
  { id: 'progress', token: 'progress', title: '공정 실적', instructions: [
    '호선과 공정을 선택합니다. 완료 공정도 보려면 완료 공정 포함을 선택합니다.',
    '공정에 마우스를 올려 최근 실적을 확인하고, 클릭해 전체 이력을 봅니다.',
    '입력 권한이 있으면 작업일, 누적 진척률, 공수와 인원을 입력하고 실적 저장을 누릅니다.',
  ] },
  { id: 'dwg-list', token: 'dwg-list', title: '도면 관리', instructions: [
    '호선·분야·상태를 선택하거나 도면 번호와 이름으로 검색합니다.',
    '도면 상세에서 리비전과 PDF를 확인합니다. 권한이 있으면 새 리비전을 작성하고 결재를 요청합니다.',
  ] },
  { id: 'dwg-approval', token: 'dwg-approval', title: '도면 결재', instructions: [
    '결재 목록에서 도면과 리비전을 선택해 검토합니다.',
    '할당된 역할에 따라 승인 또는 반려를 처리합니다. 승인된 도면은 권한이 있는 사용자가 배포합니다.',
  ] },
  { id: 'inquiry', token: 'inquiry', title: '건의·문의', instructions: [
    '건의·문의 화면이나 챗봇의 건의하기·문의하기 버튼으로 내용을 접수합니다.',
    '목록에서 접수 상태와 답변을 확인합니다. 관리자는 상태와 답변을 처리할 수 있습니다.',
  ] },
  { id: 'user-mgmt', token: 'user-mgmt', title: '회원 관리', instructions: [
    '회원 목록에서 계정과 승인 상태를 확인합니다.',
    '관리 권한이 있으면 그룹과 메뉴별 권한을 조정하고 저장합니다.',
  ] },
  { id: 'usage-log', token: 'usage-log', title: '사용 로그', instructions: [
    '조회 기간과 사용자를 선택해 화면별 이용 내역을 확인합니다.',
  ] },
  { id: 'chat', title: '챗봇', instructions: [
    '왼쪽 아래 배 캐릭터를 누르고 호선 정보, 도면 정보, 공정 실적 중 하나를 선택합니다.',
    '결과 카드에서 보고 싶은 항목을 고릅니다. 건의·문의 접수와 매뉴얼 열기도 할 수 있습니다.',
  ] },
]
const visible = computed(() => steps.filter(entry => !entry.token || menuByToken(entry.token)))
const selected = ref(props.section)
const current = computed(() => visible.value.find(entry => entry.id === selected.value) ?? visible.value[0])
</script>

<style scoped>
.manual-intro { margin: 0 0 12px; color: var(--muted); }
.manual-nav { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.manual-step { border-top: 1px solid var(--line); padding-top: 12px; }
.manual-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.manual-head h2 { margin: 0; font-size: 17px; }
.manual-step ol { padding-left: 24px; line-height: 1.7; }
.manual-step figure { margin: 16px 0 0; }
.manual-step img { display: block; width: 100%; border: 1px solid var(--line); border-radius: 8px; }
.manual-step figcaption { margin-top: 6px; font-size: 12px; color: var(--muted); }
</style>
