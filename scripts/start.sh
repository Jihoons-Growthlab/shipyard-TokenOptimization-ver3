#!/usr/bin/env bash
# 상태 확인과 세션 시작. 인자 없음: 다음 phase 안내(전부 끝났으면 exit 3) / --launch [--force] [--dry-run]: 새 Claude 세션 실행 / claim <sid>: /build 전용
set -euo pipefail
W="$(cd "$(dirname "$0")" && pwd)/wf.py"
case "${1:-}" in
  claim)    exec python3 "$W" claim "${2:-}" ;;
  --launch) shift; exec python3 "$W" launch "$@" ;;
  status)   exec python3 "$W" status ;;
  *)        exec python3 "$W" next ;;
esac
