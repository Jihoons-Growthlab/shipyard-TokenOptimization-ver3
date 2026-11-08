# SWP Shipyard — Ver3

조선소 통합관리 시스템을 `specs/`만으로 구현한다. Stack: FastAPI, Vue 3, SQLite, Unity Web. 진행은 `/build`가 phase 단위로 한다.

## 원칙
- 기능·화면·수용 기준은 명세와 `reference/ui/`를 따른다. 줄이거나 미루지 않는다. 명세에 없는 값은 지어내지 않고 `specs/index.md` 기준을 따른다.
- 검증·권한·업무 규칙은 백엔드가 소유하고 공통 규칙은 한 곳에 둔다. 내부 코드는 중복 없이 설계한다.
- 실행하지 않은 테스트, 보지 않은 화면을 완료로 보고하지 않는다. 픽셀 차이 수치만으로 화면이 맞다고 하지 않는다.

## 경로
- `specs/`, `reference/`는 원본에 연결된 읽기 전용 링크다. 그 밖의 Ver3 바깥 경로는 읽지 않는다.
- 상태는 `state/`(스크립트가 관리, `PROGRESS.md`와 `shots.json`만 직접 쓴다), 설정은 `config/`, 로그는 `reports/logs/`(요약으로 부족할 때 해당 구간만).
- 워크플로 규약: 백엔드 진입점 `backend/app/main.py`의 `app`, CLI `init-db`(pyproject scripts), Unity 빌드 진입점 `ViewerBuild.Build`.

## 작업 방식
- 테스트·빌드는 `scripts/verify.sh`, 서버는 `scripts/dev.sh`, 브라우저는 `node scripts/shots.mjs`로만 실행한다.
- 조회는 한 응답에 모으고, 한 작업의 파일 쓰기와 검증은 같은 응답에 둔다. 계획·진행 요약을 쓰지 않는다.
- 검색은 `rg`로 소스 폴더를 좁혀 실행한다. 큰 파일은 필요한 구간만 연다. `seed.json`은 코드로 적재한다.

## Compact Instructions
요약에 남길 것: 현재 phase와 남은 작업 ID, 미해결 오류(증상·명령·파일·로그 경로), 검증 상태(통과·실패·미실행). 완료 작업의 세부와 해결된 시행착오는 남기지 않는다. 압축 뒤에는 `scripts/start.sh claim`을 다시 실행해 상태를 받는다.
