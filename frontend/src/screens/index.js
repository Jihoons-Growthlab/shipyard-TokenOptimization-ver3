// 화면 토큰 → 컴포넌트. 모든 화면은 props {token,param,ctx,canWrite,title}을 받는다.
import PlaceholderScreen from './PlaceholderScreen.vue'
import DashboardScreen from './DashboardScreen.vue'
import HullListScreen from './HullListScreen.vue'
import PlanGanttScreen from './PlanGanttScreen.vue'
import ProgressScreen from './ProgressScreen.vue'
import DrawingListScreen from './DrawingListScreen.vue'
import ApprovalScreen from './ApprovalScreen.vue'
import UserMgmtScreen from './UserMgmtScreen.vue'

export { PlaceholderScreen }
export const screens = {
  dashboard: DashboardScreen,
  'hull-list': HullListScreen,
  'plan-gantt': PlanGanttScreen,
  progress: ProgressScreen,
  'dwg-list': DrawingListScreen,
  'dwg-approval': ApprovalScreen,
  'user-mgmt': UserMgmtScreen,
}
