<template>
  <div class="auth">
    <img class="scene" :src="sceneUrl" alt="" aria-hidden="true" />
    <div class="dim"></div>
    <section class="intro">
      <div class="glow"></div>
      <div class="eyebrow">⚓ SWP SHIPYARD</div>
      <h1 class="headline">설계부터 인도까지,<br />조선소 운영을 한곳에서</h1>
      <ul>
        <li><b>호선</b><span>호선별 진척률과 인도 일정을 한눈에</span></li>
        <li><b>공정</b><span>간트 계획부터 일별 실적까지</span></li>
        <li><b>도면</b><span>리비전·결재·배포 이력 관리</span></li>
      </ul>
    </section>

    <form v-if="mode === 'login'" class="acard" @submit.prevent="login">
      <div class="logo">SWP SHIPYARD</div>
      <h1>조선소 통합관리</h1>
      <p class="sub">호선 · 공정 · 도면 관리 시스템</p>
      <label class="af"><span>아이디</span><input v-model.trim="empNo" name="emp_no" autocomplete="username" autofocus /></label>
      <label class="af"><span>비밀번호</span><input v-model="password" name="password" type="password" autocomplete="current-password" /></label>
      <div class="err">{{ error }}</div>
      <button class="go" type="submit" :disabled="busy">로그인</button>
      <div class="foot">
        <a class="lnk" href="#" @click.prevent="go('signup')">회원가입</a>
        <span>구글 2차 인증 사용 계정은 다음 단계에서 OTP 입력</span>
      </div>
    </form>

    <form v-else-if="mode === 'otp'" class="acard" @submit.prevent="verify">
      <div class="logo">2-STEP VERIFICATION</div>
      <h1>구글 2차 인증</h1>
      <p class="sub">Google Authenticator 앱에 표시된 6자리 코드를 입력하세요.</p>
      <label class="af"><span>인증 코드</span><input v-model.trim="code" class="otp" name="code" inputmode="numeric" maxlength="6" autocomplete="one-time-code" autofocus /></label>
      <div class="err">{{ error }}</div>
      <button class="go" type="submit" :disabled="busy">확인</button>
      <div class="foot"><a class="lnk" href="#" @click.prevent="go('login')">← 로그인으로</a></div>
    </form>

    <form v-else class="acard wide" @submit.prevent="register">
      <div class="logo">SIGN UP</div>
      <h1>회원가입</h1>
      <p class="sub">가입 후 관리자 승인이 완료되면 로그인할 수 있습니다.</p>
      <div class="grid2">
        <label class="af"><span>성</span><input v-model.trim="reg.last_name" name="last_name" /></label>
        <label class="af"><span>이름</span><input v-model.trim="reg.first_name" name="first_name" /></label>
        <label class="af"><span>생년월일</span><input v-model="reg.birth_date" name="birth_date" type="date" /></label>
        <label class="af"><span>전화번호</span><input v-model.trim="reg.phone" name="phone" placeholder="010-0000-0000" /></label>
        <label class="af"><span>이메일</span><input v-model.trim="reg.email" name="email" type="email" /></label>
        <label class="af"><span>아이디</span><input v-model.trim="reg.emp_no" name="new_emp_no" autocomplete="off" /></label>
        <label class="af"><span>비밀번호</span><input v-model="reg.password" name="new_password" type="password" autocomplete="new-password" /></label>
        <label class="af"><span>비밀번호 확인</span><input v-model="reg.password_confirm" name="password_confirm" type="password" autocomplete="new-password" /></label>
      </div>
      <div class="err">{{ error }}</div>
      <button class="go" type="submit" :disabled="busy">가입 신청</button>
      <div class="foot"><a class="lnk" href="#" @click.prevent="go('login')">← 로그인으로</a></div>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, tokenStore } from '../api/client.js'
import { toast } from '../stores/session.js'
import sceneUrl from '../assets/auth-scene.svg'

const router = useRouter()
const mode = ref('login')
const empNo = ref('')
const password = ref('')
const code = ref('')
const error = ref('')
const busy = ref(false)
let otpToken = null
const blankReg = () => ({ last_name: '', first_name: '', birth_date: '', phone: '', email: '', emp_no: '', password: '', password_confirm: '' })
const reg = reactive(blankReg())

function go(m) {
  mode.value = m
  error.value = ''
  code.value = ''
  if (m === 'signup') Object.assign(reg, blankReg())
}

async function run(fn) {
  busy.value = true
  error.value = ''
  try { await fn() } catch (e) { error.value = e.message } finally { busy.value = false }
}

function enter(res) {
  tokenStore.set(res.access_token)
  router.replace('/')
}

const login = () => run(async () => {
  const res = await api.post('/api/auth/login', { emp_no: empNo.value, password: password.value }, { auth: false })
  if (res.otp_required) {
    otpToken = res.otp_token
    password.value = ''
    go('otp')
  } else enter(res)
})

const verify = () => run(async () => enter(await api.post('/api/auth/otp/verify', { code: code.value }, { token: otpToken })))

const register = () => run(async () => {
  await api.post('/api/auth/register', { ...reg }, { auth: false })
  go('login')
  toast('가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다.', 'success')
})
</script>

<style scoped>
.auth { position: relative; min-height: 100%; background: #060f22; display: flex; align-items: center; justify-content: space-between; gap: 48px; padding: 40px clamp(28px, 7vw, 120px); overflow: hidden; }
.scene { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: 50% 100%; pointer-events: none; }
.dim { position: absolute; inset: 0; pointer-events: none; }
.intro { position: relative; z-index: 1; margin-bottom: 22vh; color: #fff; min-width: 0; }
.glow { position: absolute; inset: -60px -80px; background: radial-gradient(ellipse at 40% 50%, rgba(6, 15, 34, .78), rgba(6, 15, 34, 0) 70%); z-index: -1; }
.eyebrow { font-size: 13px; font-weight: 700; letter-spacing: 3px; color: #8cc1f2; margin-bottom: 14px; }
.headline { font-size: clamp(28px, 3.1vw, 42px); font-weight: 700; color: #fff; line-height: 1.3; }
.intro ul { list-style: none; padding: 0; margin: 36px 0 0; width: 520px; max-width: 100%; }
.intro li { display: flex; gap: 32px; padding: 9px 0; border-top: 1px solid rgba(140, 193, 242, .25); font-size: 13.5px; color: #dbe7f5; }
.intro li b { color: #8cc1f2; }
.acard { position: relative; z-index: 2; flex: none; width: 400px; max-width: 100%; background: #fff; border-radius: 14px; padding: 32px 32px 28px; box-shadow: 0 24px 60px rgba(0, 0, 0, .45); }
.acard.wide { width: 560px; }
.logo { font-size: 12px; font-weight: 700; letter-spacing: 2px; color: var(--pri); }
.acard h1 { font-size: 22px; color: var(--navy); margin: 6px 0 4px; }
.sub { margin: 0 0 18px; color: var(--muted); font-size: 12px; }
.af { display: flex; flex-direction: column; gap: 5px; margin-bottom: 10px; font-size: 12px; color: var(--muted); }
.af input { height: 38px; width: 100%; border-radius: 6px; }
.otp { height: 46px !important; font-size: 22px; text-align: center; letter-spacing: 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.err { min-height: 20px; color: var(--err); font-size: 12px; margin: -2px 0 6px; }
.go { width: 100%; height: 42px; border: 0; border-radius: 6px; background: var(--pri); color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
.go:hover:not(:disabled) { background: var(--pri-d); }
.go:disabled { opacity: .6; }
.foot { display: flex; gap: 12px; margin-top: 12px; font-size: 12px; color: var(--muted); }
@media (max-width: 1000px) {
  .auth { justify-content: center; padding: 40px 16px; }
  .intro { display: none; }
  .dim { background: rgba(6, 15, 34, .35); }
}
</style>
