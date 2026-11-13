# Claude Code 독립 구현 명세 패키지

앱 소스가 없는 상태에서 Claude Code가 직접 backend, frontend, Unity와 테스트를 작성하는 작업이다.

## 실행
1. 이 폴더 전체를 기존 프로젝트 밖의 새 작업 폴더에 복사한다.
2. 그 폴더에서 Claude Code를 실행한다.
3. 아래 요청을 입력한다.

> CLAUDE.md를 읽고 python3 tools/session.py next로 시작해 줘. 제공된 명세·화면·API 계약·시드만으로 앱과 테스트를 처음부터 작성해. 기존 GitHub나 다른 폴더의 구현 코드를 가져오지 마. 단계별 검증과 인계 기록을 남겨 줘.

## 자료
- specs — F01~F10 업무 계약, 데이터 모델, 최신 추가 기능, 수용 시나리오
- specs/api — 단계별로 필요한 API 계약 JSON. 입력 스키마와 경로를 확인할 때 해당 파일만 읽는다.
- reference/ui — 화면 디자인 참고 이미지
- reference/seed — 시연용 데이터. JSON이며 앱 구현 코드가 아니다.
- phases — 7개 단계의 읽기 목록과 완료 조건
- tools/session.py — 구현 진행·검증 로그 관리 도구. 앱 기능을 제공하지 않는다.
- state/HANDOFF.md — 다음 세션이 읽을 짧은 인계

## 세션 운영
P1부터 단계별로 구현한다. 단계 안에서는 필요한 파일만 읽고 한 번 검증한 성공 로그를 반복 출력하지 않는다. 다음 단계는 새 세션에서 시작하며 실패한 단계는 인계를 읽고 복구한다. 공통 지침은 짧게 유지하고 전체 명세와 API 파일을 매번 로드하지 않는다.

python3 tools/session.py check backend -- uv run --directory backend pytest -q
python3 tools/session.py check frontend -- npm --prefix frontend test
python3 tools/session.py check build -- npm --prefix frontend run build
python3 tools/session.py finish P1 --evidence state/logs/backend.json

위 명령은 해당 앱과 검증 도구를 구현·설치한 뒤 실행한다. finish의 성공 명령 증거 외에도 단계별 수용 시나리오를 모두 확인한다. 불완전한 기능을 통과 처리하지 않는다.

## 범위와 기준
직접 작성할 산출물은 API·업무 서비스·DB 마이그레이션·프런트 컴포넌트·Unity C#·MCP 서버·로컬 모델 연결·테스트·실행 스크립트다. 설계·기능은 제공된 요구사항을 따르며 소스 복사 방식의 재구축은 허용하지 않는다. 공개 라이브러리와 공식 문서는 사용할 수 있다.
Ollama 모델 설치와 Unity WebGL 빌드를 수행해야 한다. 화면 참고 이미지는 시연 자료이며 외부 공개 전 표시 데이터를 검토한다. 토큰 절감률은 실제 사용량으로 측정한다.

공식 참고
- https://code.claude.com/docs/en/costs
- https://code.claude.com/docs/en/memory
