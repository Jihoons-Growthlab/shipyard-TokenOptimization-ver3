# 인계
- 완료: P1 (백엔드 전 API), P2 (인증·셸·호선·공정 계획·실적), P3 (도면·결재·회원관리·대시보드), P4 (T20 Unity 뷰어·3D 탭, T21 최종 수용) / 다음: 없음
- 환경: node v24.16.0, npm 11.13.0, uv 0.13.7, Chrome 있음, Unity 6000.5.10f1 + WebGL(라이선스 -createProject로 확인). 백엔드 venv Python 3.10.

## 결정·인터페이스
- 공통 규칙 `backend/app/services/rules.py`, 권한 `deps.require(menu, level)`. API 403 `권한이 없습니다.`, 프론트 거부 `해당 화면에 대한 권한이 없습니다.`
- OTP: 토큰당 5회 실패까지 400, 이후 429. 같은 30초 step 재로그인은 400.
- 저장소 키: sessionStorage `swp_token`, `swp_tabs`, localStorage `swp_region`.
- 화면 이동: 셸 `provide('navigate', (token,param)=>…)`, 같은 탭이면 `ctx` 증가 → `watch(ctx)`.
- 도면 상세 모달 `screens/DrawingDetail.vue` 재사용(목록·간트·결재함·대시보드).
- Unity: 프로젝트 `unity/ShipyardViewer`, Editor `Assets/Editor/ViewerBuild.cs`가 재질(Assets/Generated)·씬 재생성 + WebGL 빌드 → `frontend/public/unity/ship-viewer/Build/` (+`build.json`, Build 기준 상대, 14.4MB).
- 런타임 `Assets/Scripts/ShipModel.cs`(메시·상자), `ShipViewer.cs`(궤도 카메라·SetView·준비 신호), `Plugins/WebGL/ShipViewer.jslib`.
- 프론트 수명주기 `src/utils/unityViewer.js`(startViewer/stop 체인, 단일 인스턴스), 탭 UI `components/ShipViewer3D.vue`(canvas id `ship-viewer-canvas-<n>`, 재시도 시 n 증가).
- 호선 상세 서브탭 `viewer`(3D 보기)일 때 모달 size `xl`. 3D 탭 왕복은 재조회하지 않아 작성 내용 유지(`lastDataTab`).
- shots: 플로는 account+viewport 그룹 단위 실행. 계정 교대는 viewport 1px 차이로 순서를 강제. 3D 준비 대기 `.views button:not([disabled])`.

## 검증
- 통과: backend 86, frontend vitest 40(뷰어 10: 로더 실패·재시도, SPA 폴백, 타임아웃, 지연 완료 Quit, 8회 반복 누적 없음, 3D 왕복 입력 유지), build PASS, unity build PASS.
- shots 전체 45 flows(fresh DB): 시나리오 전부 pass(가입→승인→로그인, 승인대기 거절, 호선 등록·삭제, 공정 추가·도면 연계, 실적 100%→완료, 결재 2단계→배포, 3D 8회 왕복+Esc, 조회 전용 3D).
- 3D 화면 직접 확인: 초기·측면·정면·상단·초기화 렌더가 기준 이미지와 일치(diff 0.02~0.03), reset 후 hull-3d 재비교 ok.
- Vite dev에서 `.wasm` Content-Type `application/wasm` 확인.
- 미실행: Vite preview 실행(dev.sh에 preview 모드 없음), 마우스 드래그·휠 조작과 범위 한계(shots 단계에 드래그 없음 — 코드상 범위 clamp만 확인), 창 크기 변경 추종(Unity 기본 matchWebGLToCanvasSize 의존).

## 미해결
- signup shot over(0.108): 명세 카드 폭 560px 우선 수용(P2).
- ship-side/front/top: 뷰어 clip 1090x696 vs 기준 1088x696(모달 xl 폭 반올림 2px). 내용 diff는 0.02~0.033.
- Unity 배치 종료 후 UnityPackageManager 서버 프로세스가 남아 verify가 출력 대기로 멈출 수 있다 → 해당 PID만 종료(다른 프로젝트 Editor의 UPM은 건드리지 않음). createProject는 종료 시 exit 134(정상 종료 로그 뒤 크래시).
- 대시보드 호선 라벨 130px 말줄임(명세 그대로). pytest 경고 1건(starlette TestClient).
