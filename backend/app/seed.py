"""init-db CLI: 마이그레이션 적용 후 (--seed) seed.json을 PK 그대로 적재. 반복 실행해도 안전하다."""
import argparse
import json

from . import config
from .db import connect, migrate, tx
from .security import hash_password


def load_seed(conn, path=None) -> dict:
    data = json.loads((path or config.SEED_FILE).read_text(encoding="utf-8"))
    existing_users = {r[0] for r in conn.execute("SELECT emp_no FROM users")}
    counts = {}
    with tx(conn):
        for table, spec in data.items():
            cols, rows = list(spec["columns"]), spec["rows"]
            if table == "users":
                pw_i = cols.index("demo_password")
                emp_i = cols.index("emp_no")
                cols = [c for c in cols if c != "demo_password"] + ["password_hash"]
                rows = [[v for i, v in enumerate(r) if i != pw_i] + [hash_password(r[pw_i])]
                        for r in rows if r[emp_i] not in existing_users]
            sql = f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
            conn.executemany(sql, rows)
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="init-db")
    ap.add_argument("--seed", action="store_true", help="seed.json 적재")
    args = ap.parse_args(argv)
    conn = connect()
    try:
        applied = migrate(conn)
        print(f"db={config.db_path()} migrations applied={applied or 'none'}")
        if args.seed:
            counts = load_seed(conn)
            print("seed:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
