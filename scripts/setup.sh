#!/usr/bin/env bash
# 최초 1회: specs/reference 연결(읽기 전용), 상위 CLAUDE.md 제외 설정, 측정 조건 기록, playwright-core 설치.
# 사용: scripts/setup.sh [명세 원본 폴더(기본: Ver3의 상위 폴더)]
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="$(cd "${1:-..}" && pwd)"
[ -d "$SRC/specs" ] && [ -d "$SRC/reference" ] || { echo "specs/, reference/가 없다: $SRC" >&2; exit 1; }
for d in specs reference; do
  if [ -L "$d" ]; then rm "$d"; elif [ -e "$d" ]; then echo "$d가 링크가 아니다. 확인 후 지운다." >&2; exit 1; fi
  ln -s "$SRC/$d" "$d"
done
# 상위 폴더의 CLAUDE.md를 로드하지 않도록 절대 경로로 제외한다(Ver2 지침이 섞이지 않게).
python3 - <<'PY'
import json, os
root = os.getcwd(); ex = []; d = os.path.dirname(root)
while d != os.path.dirname(d):
    for n in ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md"):
        if os.path.exists(os.path.join(d, n)): ex.append(os.path.join(d, n))
    d = os.path.dirname(d)
p = ".claude/settings.local.json"
cur = json.load(open(p)) if os.path.exists(p) else {}
cur["claudeMdExcludes"] = ex
json.dump(cur, open(p, "w"), indent=2); print("claudeMdExcludes:", ex or "없음")
PY
{
  echo "prepared_at=$(date +%FT%T%z)"
  echo "path=$PWD"
  echo "spec_source=$SRC"
  echo "specs_sha256=$(cd "$SRC" && find specs -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
  echo "reference_sha256=$(cd "$SRC" && find reference -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
  echo "claude_version=$(claude --version 2>/dev/null || echo unknown)"
} > state/conditions.txt
[ -d scripts/node_modules/playwright-core ] || npm install --prefix scripts --no-audit --no-fund --silent
cat state/conditions.txt
echo "준비 완료. 시작: scripts/start.sh --launch"
