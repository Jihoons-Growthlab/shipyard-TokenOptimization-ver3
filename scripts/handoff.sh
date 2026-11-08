#!/usr/bin/env bash
# 완료 기록: task <TID> | phase [--accept-shots <이유>] | block <TID> <사용자 조치>. 검증 기록이 없으면 거부한다.
set -euo pipefail
W="$(cd "$(dirname "$0")" && pwd)/wf.py"
case "${1:-}" in
  task)  exec python3 "$W" done-task "${2:-}" ;;
  phase) shift; exec python3 "$W" handoff-phase "$@" ;;
  block) shift; exec python3 "$W" block "$@" ;;
  *) echo "usage: handoff.sh task <TID> | phase [--accept-shots <reason>]"; exit 1 ;;
esac
