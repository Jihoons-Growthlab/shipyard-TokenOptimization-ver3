#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
export SHIPYARD_DB_PATH=state/run/demo.db
export SHIPYARD_FILE_DIR=state/run/demo-files
export SHIPYARD_DEMO=1

if [[ ! -f ../state/run/demo.db ]]; then
  .venv/bin/init-db --seed --demo-pdfs --demo-usage
  .venv/bin/python - <<'PY'
from app.db import connect, tx
from app.security import hash_password

conn = connect()
try:
    with tx(conn):
        conn.execute("UPDATE users SET status='disabled'")
        conn.execute("""UPDATE users SET status='approved', totp_enabled=0, totp_secret=NULL,
                         password_hash=? WHERE emp_no IN ('admin', 'han.wk')""", (hash_password("Shipyard-Demo-26!"),))
finally:
    conn.close()
PY
fi
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
