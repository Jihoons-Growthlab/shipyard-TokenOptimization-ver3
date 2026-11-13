# Claude Code용 조선소 재구축 패키지

현재 앱의 기능을 보존하면서 반복 읽기와 도구 출력을 줄이는 실행 패키지다.

## 시작
1. 이 폴더 전체를 기존 프로젝트 밖의 새 폴더로 복사한다. 상위 CLAUDE.md가 상속되지 않는 위치를 쓴다.
2. 새 폴더에서 Claude Code를 시작한다.
3. 아래 문장을 전달한다.

> CLAUDE.md를 따르고 python3 tools/session.py next로 현재 단계를 확인해 구현해 줘. 최신 계약은 specs/DELTA.md야. 해당 단계의 baseline과 테스트만 참고하고 기능 구현 후 검증해. 실제 통과한 항목만 완료 기록하고 다음 세션에 필요한 인계를 남겨 줘.

4. 단계가 끝나면 새 세션에서 같은 요청을 반복한다.

## 포함 자료
- specs/ — 기존 F01~F10, 데이터·규칙·UI 원문 사본과 최신 추가 계약
- baseline/ — 2026-11-13 로컬 작업 트리의 미커밋 변경까지 포함한 앱·테스트·Unity 소스
- reference/ui/ — 기존 화면 예시
- reference/seed/seed.json — 연락처와 인증값을 시연용으로 치환한 시드
- reference/SHA256.json — 기준 파일 해시
- phases/ — 단계별 최소 읽기 목록
- tools/session.py — 단계 선택, 검증 로그 요약, 완료 증거 기록
- state/HANDOFF.md — 짧은 세션 인계

## 구현 위치
새 루트에 backend/, frontend/, database/, unity/를 만든다. baseline 파일을 선택적으로 재사용할 수 있다. baseline 자체는 수정하지 않는다. 전체 baseline 복사만으로 완료 처리하지 않는다. 기본 모델 가중치와 Unity WebGL 산출물은 새 환경에서 설치·빌드한다.

## 세션·토큰 정책
공통 지침은 짧고 안정적으로 유지하고 단계 문서는 필요할 때만 읽는다. 실패 로그의 관련 구간만 읽고 수정한다. 같은 컨텍스트 안에서 반복 질문·전체 재탐색을 피한다. 단계당 대표 화면을 확인하고 최종 단계에서 전체 사용자 흐름을 검증한다. 오류 수정을 두 번 시도한 후에는 실패 근거와 가설을 정리하되 임의 완료 처리하지 않는다.
현재 설치된 Claude Code의 지원 모델·권한 설정을 확인해 선택한다. 오래된 모델명이나 추론 옵션을 강제하지 않는다. 기본은 단일 에이전트다. /usage 등 실제 제공되는 사용량 표시로 입력·출력·캐시·세션 수·재시도를 기록한다. 고정 절감률은 보장하지 않는다.

## 검증 명령 사용
python3 tools/session.py check backend -- uv run --directory backend pytest -q
python3 tools/session.py check frontend -- npm --prefix frontend test
python3 tools/session.py check build -- npm --prefix frontend run build
python3 tools/session.py finish P1 --evidence state/logs/backend.json

check는 로그를 저장하고 실패 시 마지막 30줄만 출력한다. finish는 성공한 명령 증거를 확인한다. 사용자 흐름과 화면 검증의 증거는 ACCEPTANCE.md에 기록한다. 성공한 테스트 하나가 단계 전체 완성을 보장하지 않으므로 해당 단계 수용 항목을 모두 확인한다.

## 출처·이동성
GitHub https://github.com/Jihoons-Growthlab/shipyard-TokenOptimization-ver3
현재 로컬 추가 구현이 GitHub보다 최신일 수 있다. 기존 specs/reference 심볼릭 링크를 실제 파일로 담았다. 실제 DB·첨부·로그·환경 비밀값·Ollama 가중치는 제외했다. 캡처에 있는 표시명과 업무 데이터는 외부 공개 전 검토한다. 기존 테스트의 시드 인증값 가정은 제공된 시드에 맞춰 조정한다.

공식 운영 참고
- https://code.claude.com/docs/en/costs
- https://code.claude.com/docs/en/memory

이 패키지의 검증은 명세와 실행 도구에 대한 검증이다. 재구축 앱은 P7 수용 검증 후에 완료된다.
