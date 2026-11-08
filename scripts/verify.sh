#!/usr/bin/env bash
# 테스트·빌드 실행: <backend|frontend|build|unity|all> [추가 인자] [--dry-run]. 전체 로그는 reports/logs/, 출력은 요약과 실패 줄만.
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/wf.py" verify "$@"
