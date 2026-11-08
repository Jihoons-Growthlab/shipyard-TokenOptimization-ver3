# Ver3 — 저토큰 빌드 워크플로

같은 명세(`specs/`, `reference/`)로 SWP Shipyard를 구현하는 두 번째 실험. Ver2가 "지침으로 LLM에게 아껴 쓰라고 부탁"했다면, Ver3는 **판단이 필요 없는 일을 스크립트로 옮겨 API 호출 수와 호출당 컨텍스트를 구조적으로 줄인다.**

## 결과 요약 (Ver2 → Ver3)

| 지표 | Ver2 | Ver3 | 변화 |
| --- | ---: | ---: | ---: |
| 총 토큰 | 39,270,601 | 11,598,368 | **−70.5%** |
| API 호출 | 276 | 92 | −66.7% |
| cache read | 37,975,461 | 10,595,880 | −72.1% |
| cache creation | 913,747 | 659,757 | −27.8% |
| output | 380,829 | 342,547 | −10.1% |
| 짧은 응답(출력 700토큰 미만) | 173 | 38 | −78.0% |
| 세션 첫 호출 컨텍스트 | 약 44K | 34~36K | 약 −20% |
| 소요 시간(첫~마지막 호출) | 1시간 55분 | 1시간 25분 | −26% |
| 목표(1천만 토큰) | — | 미달성(+16%) | |

같은 조건: 명세 해시(`specs_sha256=4cd0cc36…`, `reference_sha256=712f1c16…`), Claude Code 2.1.319, `claude-opus-5-5`, effort medium, permission mode auto. 출처: Ver2 `report_data.json`, Ver3 `report_data.json`·`reports/usage.json`.

**핵심 관찰**: 총 토큰의 96%(Ver2)·91%(Ver3)가 cache read다. cache read ≈ 호출 수 × 그 시점 컨텍스트 크기이므로, 출력량은 거의 그대로(−10%)인데 **호출 수를 1/3로 줄인 것이 절감의 대부분**이다. 호출당 평균 토큰도 142K → 126K로 줄었다.

### 세션별

| Ver2 세션 | 범위 | 토큰 | | Ver3 세션 | 범위 | 호출 | 토큰 |
| --- | --- | ---: | --- | --- | --- | ---: | ---: |
| S1 `34e639a4` | 단계 1~3 | 1.80M | | P1 `e37c4d36` | 백엔드 전체(T01~T10) | 20 | 2.93M |
| S2 `f5cc4506` | 단계 4~6 | 11.86M | | P2 `7806b69b` | 인증·셸·호선·공정·실적(T11~T15) | 17 | 2.30M |
| S3 `a82a2110` | 단계 7~8 | 9.23M | | P3 `1169bc7a` | 도면·결재·회원·대시보드(T16~T19) | 26 | 3.17M |
| S4 `ff2344b5` | 단계 9~10 | 5.16M | | P4 `b0b5ae00` | Unity·3D 탭·최종 수용(T20~T21) | 29 | 3.19M |
| S5+S6 `9688fe56` | 단계 11~12 (같은 세션 재사용) | 11.15M | | | | | |
| `bc24695b` | 종료 확인 | 0.09M | | | | | |
| **합계** | | **39.27M** | | **합계** | | **92** | **11.60M** |

Ver2는 세션당 최대 11.9M까지 튀었고, Ver3는 phase마다 2.3~3.2M으로 고르다. 세션 수를 줄인 게 아니라 **세션 하나가 커지지 않게** 만든 결과다.

### 도구 사용

| 도구 | Ver2 | Ver3 |
| --- | ---: | ---: |
| Bash | 177 | 79 |
| Read | 82 | 50 |
| Playwright MCP | 51 | 0 |
| Write | 15 | 88 |
| Edit | 1 | 15 |
| ToolSearch | 6 | 0 |

Ver2는 실행·조회·브라우저 조작(Bash+Read+MCP = 310)이 대부분이었다. Ver3는 Write·Edit(103)이 비중의 중심이 됐다. 즉 호출이 "확인하러 가는 일"에서 "만드는 일"로 옮겨갔다.

## 기법

### 1. 호출 수를 줄인다 — 한 응답에 한 작업

| Ver2 문제 | Ver3 기법 |
| --- | --- |
| 짧은 응답 173회가 약 23.2M. 조회 하나, 실행 하나마다 왕복 | 한 작업의 **파일 쓰기 전부 + `verify.sh … && handoff.sh task <TID>`를 한 응답**에 넣는다. 조회는 한 응답에 모은다 |
| 세션 시작마다 PROGRESS·index·명세·환경을 따로 읽음 | `start.sh claim` **출력 한 번**에 작업·명세 경로·이미지·PROGRESS·SOURCEMAP·환경을 모두 담는다. 이 파일들은 다시 열지 않는다 |
| 계획·진행 보고 텍스트 | 계획·진행·완료 요약을 쓰지 않는다(CLAUDE.md, SKILL.md) |

### 2. 세션이 커지지 않게 한다 — phase마다 새 프로세스

| Ver2 문제 | Ver3 기법 |
| --- | --- |
| `/clear`가 새 세션을 만들지 않아 S5·S6이 `9688fe56` 하나에 이어 쓰임(약 3.5M 추가) | `start.sh --launch`가 phase마다 **새 `claude` 프로세스**를 띄운다 |
| 사용자가 세션 전환을 직접 관리 | 같은 세션 ID로 다음 phase를 claim하면 **스크립트가 거부**(`test_wf.py`로 검증) |
| 진행 중 세션을 덮어쓸 위험 | 열린 claim의 transcript가 15분 안에 갱신됐으면 `--launch` 거부 |

### 3. 코드를 다시 탐색하지 않는다 — SOURCEMAP 자동 생성

| Ver2 문제 | Ver3 기법 |
| --- | --- |
| S2~S5에서 `.vue`·CSS를 세션마다 다시 읽음(읽기 84회) | `state/SOURCEMAP.md`(14KB 상한)를 스크립트가 생성: OpenAPI 계약, Python 공개 함수, Vue props·emits·scoped CSS, JS export, CSS 클래스, Unity, 테스트 수 |
| 기능별 세션 분할 → 매 세션 백엔드·프론트를 모두 탐색 | **계층별 분할**: P1은 백엔드 전체, P2·P3는 백엔드 코드 대신 SOURCEMAP의 API 계약만 읽는다 |
| `.vue`는 코드맵에 없어 PROGRESS에 손으로 적음 | 컴포넌트 인터페이스는 자동 생성, PROGRESS(40줄)는 SOURCEMAP에 없는 결정만 |

### 4. 기계적인 일은 스크립트가 한다

| 일 | Ver2 (LLM이 실행) | Ver3 (스크립트) |
| --- | --- | --- |
| 환경 점검 | 세션마다 명령 실행 | `state/env.json` 캐시 |
| 테스트·빌드 | 명령 실행 후 로그를 직접 읽음 | `verify.sh`: **요약과 실패 줄만** 출력, 전체 로그는 `reports/logs/` |
| 서버 | 포트·DB·시드를 매번 조립 | `dev.sh up --fresh`: 임시 DB 시드 적재·헬스체크까지 |
| 작업 완료 판정 | LLM이 PROGRESS에 기록 | `handoff.sh`가 검증 통과 시에만 `tasks.json`에 기록(LLM은 수정 불가) |
| 사용량 집계 | 별도 저장소에서 수동 집계 | `wf.py usage`: 세션별 calls·short calls·first/max ctx |

공통 구현은 `scripts/wf.py`(778줄) 하나, 자체 테스트 `scripts/test_wf.py`.

### 5. 화면 확인 반복을 끊는다

| Ver2 문제 | Ver3 기법 |
| --- | --- |
| Playwright MCP로 캡처 → 보기 → 한 줄 수정 반복(MCP 51회) | phase 끝에 `node scripts/shots.mjs --phase <P>` **한 번**. 흐름은 `state/shots.json`에 미리 정의 |
| 모든 화면 이미지를 열어 봄 | 픽셀 차이가 기준(0.08) 초과이거나 오류인 화면만 연다 |
| 수정 횟수 제한 없음 | 반복 **최대 2회**, 남은 차이는 사유와 함께 accept하거나 미해결로 기록 |

### 6. 호출당 기본 컨텍스트를 줄인다

| 항목 | Ver2 | Ver3 |
| --- | --- | --- |
| Ponytail 플러그인 | 켬(v5.3.3 full) | 끔 |
| MCP | Playwright MCP | 없음 + `--strict-mcp-config` |
| claude.ai 커넥터 | 기본 | `disableClaudeAiConnectors`, `ENABLE_CLAUDEAI_MCP_SERVERS=false` |
| 도구 | 전부 | Agent·WebSearch·WebFetch·NotebookEdit 거부 |
| 상위 폴더 CLAUDE.md | 로드될 수 있음 | `claudeMdExcludes`로 제외 |
| CLAUDE.md | 2.9KB | 1.9KB |
| 첫 호출 컨텍스트 | 약 44K | 34~36K |

### 7. 상태를 LLM이 망가뜨리지 못하게 한다

`specs/`, `reference/`, `config/`, `state/tasks.json`, `state/sessions.log`, `state/SOURCEMAP.md`는 `Edit` 거부. LLM이 직접 쓰는 상태는 `PROGRESS.md`와 `shots.json`뿐이다. 잘못된 상태를 바로잡느라 쓰는 호출을 없앤다.

## 품질 비교와 해석상 주의

| 항목 | Ver2 | Ver3 |
| --- | --- | --- |
| 백엔드 테스트 | pytest 123 | pytest 86 |
| 프론트 테스트 | vitest 52 | vitest 40 |
| 빌드 | vite build 통과 | vite build·Unity build 통과 |
| 화면 비교 | 화면별 수동 비교(S1~S6) | shots 45 flows 자동 비교, 시나리오 전부 pass |
| 미해결 | Vue 속성 경고 | signup diff 0.108(명세 폭 우선), 3D 뷰어 2px 폭 차이, 드래그·휠 미확인 |

- **테스트 수가 줄었다**(−30%, −23%). 둘 다 명세의 수용 기준 ID를 기준으로 했지만 Ver3가 테스트를 더 묶어서 썼을 수 있다. 토큰 절감이 테스트 축소에서 온 부분이 있는지는 따로 확인해야 한다.
- **변수가 여러 개 동시에 바뀌었다.** Ponytail 끔, MCP 제거, 세션 분할 방식, 스크립트화가 한 번에 들어갔기 때문에 기법별 기여도는 분리되지 않는다. 세션별 비교도 범위가 달라서(기능별 6개 대 계층별 4개) 1:1이 아니다.
- **1회 실행 결과다.** 같은 조건의 반복 실행으로 분산을 보지 않았다.
- phase 예산 25회를 P3(26)·P4(29)가 넘었다. P4는 Unity 빌드 대기와 UPM 프로세스 정리가 호출을 늘렸다.

## 다음에 줄일 곳

- **호출 수가 여전히 지배적이다.** 92회 × 평균 126K. phase 후반으로 갈수록 컨텍스트가 커지므로(max_ctx 143~235K) 큰 phase(P1·P4)를 한 번 더 나누면 후반 호출의 단가가 내려간다.
- 짧은 응답 38회(P3 15회) 중 무엇이 남았는지 transcript로 분류한다.
- 기법별 효과를 분리하려면 하나씩 되돌린 실행이 필요하다(예: Ponytail만 켜기).

---

## 구조

| 경로 | 역할 |
| --- | --- |
| `CLAUDE.md` | 매 호출 로드되는 최소 원칙 |
| `.claude/skills/build/SKILL.md` | `/build`: phase 하나를 구현하고 멈춤 |
| `.claude/settings.json` | 권한, Ponytail·MCP·claude.ai 커넥터 끔, 서브에이전트·웹 도구 거부, 명세·상태 파일 수정 거부 |
| `config/workflow.json` | 실행·검증·서비스·스크린샷·소스맵 명령과 기준값 |
| `config/token-policy.json` | 예산(실험값), 단가(미설정 시 비용 미산출) |
| `state/tasks.json` | phase 4개와 작업 21개. 완료 상태는 스크립트만 기록 |
| `state/PROGRESS.md` | 유일한 서술형 인계(40줄 이하) |
| `state/SOURCEMAP.md` | 생성물: API 계약, 공개 함수, Vue 인터페이스, CSS 클래스, Unity, 테스트 수 |
| `state/shots.json` | 화면 흐름(phase별로 `/build`가 작성) |
| `state/sessions.log` | 세션 이벤트(claim·resume·takeover·task-done·phase-done·refused) |
| `scripts/` | `start.sh`, `dev.sh`, `verify.sh`, `handoff.sh`, `shots.mjs`, `setup.sh`, 공통 구현 `wf.py`, 자체 테스트 `test_wf.py` |
| `reports/` | `usage.json`, `logs/`(전체 로그), `shots/`(캡처·diff) |

## Phase

| Phase | 작업 | 체크포인트 |
| --- | --- | --- |
| P1 | 단계 1~10의 백엔드 전체(T01~T10) | `verify backend` |
| P2 | 인증 화면, 공통 셸, 호선, 공정 계획, 실적(T11~T15) | `verify frontend,build` + shots |
| P3 | 도면, 결재, 회원관리, 대시보드(T16~T19) | `verify frontend,build` + shots |
| P4 | Unity와 3D 탭(T20), 최종 수용 검증(T21) | `verify all` + shots |

## 실행

### 1. 준비 (1회)

Ver2 폴더 밖의 새 위치에 복사해서 쓰는 것을 권장한다(Ver2 앱 코드·Git과 섞이지 않게).

```sh
cp -R <Ver2>/Ver3 <새 폴더>
cd <새 폴더>
bash scripts/setup.sh <Ver2 루트>
```

`setup.sh`는 `specs`·`reference`를 원본에 심볼릭 링크로 연결하고(읽기 전용), 상위 `CLAUDE.md`를 `claudeMdExcludes`에 넣고, 명세 해시를 `state/conditions.txt`에 기록하고, `scripts/node_modules`에 `playwright-core`를 설치한다(브라우저는 설치된 Chrome).

### 2. 진행

```sh
scripts/start.sh            # 다음 phase와 작업. 전부 끝났으면 exit 3과 사용량 출력
scripts/start.sh --launch   # 새 Claude 세션을 /build로 시작
```

세션은 phase 하나를 끝내면 `다음: /exit 후 scripts/start.sh --launch`를 출력하고 멈춘다. 4번 반복하면 끝난다. 첫 프롬프트로 `/build`가 실행되지 않으면 세션 안에서 직접 입력한다.

| 상황 | 할 일 |
| --- | --- |
| 세션이 끊겼고 대화가 필요함 | `claude --continue` 후 `/build` → claim이 `resume`으로 이어감 |
| 세션이 끊겼고 대화가 필요 없음 | `scripts/start.sh --launch --force` → `takeover`, `PROGRESS.md` 기준으로 재개 |
| 자동 압축 뒤 | `/build`가 `start.sh claim`을 다시 실행해 상태를 받음 |
| Unity 설치·라이선스 문제 | `handoff.sh block T20 "<조치>"`로 기록. 조치 후 `python3 scripts/wf.py reopen T20 "<이유>"` |
| 완료된 작업을 다시 해야 함 | `python3 scripts/wf.py reopen <TID> "<이유>"` |

### 3. 앱 직접 실행

```sh
scripts/dev.sh up --fresh   # state/run/fresh.db에 시드를 새로 적재해 실행
scripts/dev.sh status
scripts/dev.sh down
```

프론트 http://127.0.0.1:5173/, 백엔드 http://127.0.0.1:8000/api/health. 계정은 `reference/seed/seed.json`의 `users`(`demo_password`). admin·lee.dwg는 TOTP(secret `JBSWY3DPEHPK3PXP`), jung.new는 승인 대기라 거절된다.

### 4. 측정

```sh
python3 scripts/wf.py usage    # reports/usage.json
python3 extract_usage.py       # report_data.json (Ver2와 같은 형식)
```

`sessions.log`에 claim이 기록된 세션만 집계한다. 서브에이전트 transcript 포함, `message.id` 기준 중복 제거, `<synthetic>` 제외(Ver2와 같은 방식). 비용은 `config/token-policy.json`의 `pricing`을 채웠을 때만 계산한다.

## 직접 쓰는 명령

```sh
scripts/verify.sh backend tests/test_hulls.py   # 대상 테스트. 요약과 실패 줄만 출력
scripts/verify.sh all [--dry-run]                # backend + frontend + build
node scripts/shots.mjs --phase P2 [--only a,b] [--dry-run]
scripts/handoff.sh task T13 | phase [--accept-shots "<이유>"] | block T20 "<조치>"
python3 scripts/wf.py status | srcmap [--if-stale]
python3 scripts/test_wf.py                       # 워크플로 자체 테스트
```

## 한계

- 픽셀 차이는 우선 볼 화면을 고르는 신호일 뿐이다. 기준 이미지의 데이터 값은 시드 예시라 같은 화면도 차이가 날 수 있다. 최종 판단은 이미지를 보고 한다.
- `--strict-mcp-config`·커넥터 끔·도구 거부 각각이 첫 호출 컨텍스트를 얼마나 줄였는지는 분리 측정하지 않았다(합산 약 44K → 34~36K).
# shipyard-TokenOptimization-ver3
