---
name: build
description: Ver3 phase 하나를 구현하고 멈춘다. 작업 선택·완료 판정·세션 검사는 scripts가 한다.
disable-model-invocation: true
---

# /build

한 세션 = 한 phase. 상태 판단은 스크립트 출력만 따른다.

1. **시작**: `bash scripts/start.sh claim "${CLAUDE_SESSION_ID}"`만 실행한다. 출력이 이번 phase의 작업·명세·이미지·`PROGRESS.md`·`SOURCEMAP.md`·환경 전부다. 이 파일들을 다시 열지 않는다.
   - exit 3 `ALL_DONE`: `state/PROGRESS.md`의 통과·실패·미실행과 차단 작업을 보고하고 멈춘다.
   - exit 2 `REFUSED`: 안내 문장을 그대로 전하고 멈춘다.
2. **읽기 (한 응답)**: pending 작업의 명세와 이미지를 한 응답에서 함께 Read한다. 기존 코드는 SOURCEMAP에서 경로를 찾아 수정할 파일만 연다.
3. **구현 (작업마다 1~2 응답)**: 한 작업의 파일을 한 응답에서 모두 Write/Edit하고, 같은 응답의 마지막 호출로
   `scripts/verify.sh <대상> [관련 테스트 경로] && scripts/handoff.sh task <TID>`를 실행한다.
   실패하면 출력된 요약으로 고친다. 로그는 요약이 부족할 때만 해당 구간을 본다. 파일을 공유하는 작업은 묶어도 된다.
4. **체크포인트 (phase 끝 1회)**:
   - 인자 없이 `scripts/verify.sh <checkpoint 대상>`.
   - 화면 phase: `state/shots.json`에 이번 phase 화면 흐름을 한 번에 추가하고 `scripts/dev.sh up --fresh && node scripts/shots.mjs --phase <P>`.
   - `over`·`error`인 화면만 `reports/shots/<name>.png`, `.diff.png`, 기준 이미지를 한 응답에서 본다. 고칠 것을 모아 한 번에 고치고 다시 실행한다. 반복은 2회까지다.
   - 남은 차이가 시드 값·애니메이션처럼 명세상 정당하면 `handoff.sh phase --accept-shots "<이유>"`, 아니면 `PROGRESS.md` 미해결에 적는다.
5. **인계 (한 응답)**: `state/PROGRESS.md`를 덮어쓰고(40줄 이내, SOURCEMAP에 없는 결정·저장소 키·화면 이동 방식·미해결만) 같은 응답에서 `scripts/handoff.sh phase`. 거부되면 사유만 해결한다.
6. **멈춤**: 마지막 줄에 `다음: /exit 후 scripts/start.sh --launch`를 출력한다. 다음 phase를 이 세션에서 시작하지 않는다.

## 규칙

- 조회 하나만 하는 응답을 만들지 않는다. 필요한 조회·실행은 한 응답에 모은다.
- 계획, 진행 보고, 완료 요약을 쓰지 않는다. 서브에이전트, 리뷰·감사, Playwright MCP를 쓰지 않는다.
- 테스트·빌드는 `verify.sh`, 서버는 `dev.sh`, 브라우저는 `shots.mjs`로만 돌린다.
- done 작업은 다시 하지 않는다. 앞 phase 코드의 결함을 고쳤으면 해당 검증을 다시 통과시킨다.
- 예산(phase당 약 25회 호출)은 실험값이다. 기능·테스트·화면 확인을 줄이는 근거가 아니다.
- 설치·라이선스처럼 사용자만 할 수 있는 조치가 필요하면 `scripts/handoff.sh block <TID> "<조치>"`, `PROGRESS.md`에 기록하고 나머지를 진행한다.

## state/shots.json

```json
{"auth": {"storage": "sessionStorage", "key": "<프론트가 토큰을 두는 키>"},
 "flows": [{"name": "hull-list", "phase": "P2", "account": "park.pm", "ref": "hull-list.png",
            "viewport": [1440, 900], "clip": null, "threshold": 0.08,
            "steps": [{"goto": "/"}, {"click": "text=호선관리"}, {"wait": ".hull-table"}]}]}
```

- `account`가 있으면 API로 로그인한다(시드 비밀번호, OTP는 RFC 6238 자동 계산). 없으면 비로그인 상태다.
- steps: `goto`, `click`, `fill [sel,값]`, `press [sel,키]`, `select [sel,값]`, `wait sel|ms`, `expect 텍스트`, `expectNot 텍스트`.
- `ref`가 없는 흐름은 시나리오 검사(단계 성공 여부)다. 데이터를 바꾸는 흐름은 `dev.sh up --fresh` 위에서만 실행한다.
