#!/usr/bin/env bash
# 백엔드·프론트 서비스: up [--fresh] | down | status. --fresh는 state/run/fresh.db에 시드를 새로 적재한다.
set -euo pipefail
exec python3 "$(cd "$(dirname "$0")" && pwd)/wf.py" dev "$@"
