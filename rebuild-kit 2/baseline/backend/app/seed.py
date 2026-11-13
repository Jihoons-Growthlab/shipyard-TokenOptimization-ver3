"""init-db CLI: 마이그레이션 적용 후 (--seed) seed.json을 PK 그대로 적재. 반복 실행해도 안전하다."""
import argparse
import json

from . import config
from .db import connect, migrate, tx
from .security import hash_password


# seed.json(읽기 전용 원본) 뒤에 덧붙이는 행(명세 외 요청 기능): 사용 로그·건의·문의 메뉴와 권한.
EXTRA_ROWS = {
    "TB_SYS_MenuInfo": (["MenuId", "SystemId", "ParentId", "Title", "TokenUrl", "Seq", "UseYN"], [
        ["M92", "SHIP", "M90", "사용 로그", "usage-log", 12, 1],
        ["M95", "SHIP", None, "건의·문의", "inquiry", 13, 1],
    ]),
    "TB_SYS_AuthMenu": (["MenuId", "AuthCd", "AuthGbn"], [
        ["M92", "ADMIN", "Admin"], ["M95", "ADMIN", "Admin"],
        ["M95", "PROC", "Write"], ["M95", "DWG", "Write"], ["M95", "VIEW", "Write"],
    ]),
}


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
        for table, (cols, extra) in EXTRA_ROWS.items():
            conn.executemany(f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", extra)
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="init-db")
    ap.add_argument("--seed", action="store_true", help="seed.json 적재")
    ap.add_argument("--demo-pdfs", action="store_true", help="파일 없는 도면 리비전에 예시 PDF 첨부(개발·시연용)")
    ap.add_argument("--demo-usage", action="store_true", help="예시 사용 로그(30일)·건의 글 적재(개발·시연용)")
    args = ap.parse_args(argv)
    conn = connect()
    try:
        applied = migrate(conn)
        print(f"db={config.db_path()} migrations applied={applied or 'none'}")
        if args.seed:
            counts = load_seed(conn)
            print("seed:", ", ".join(f"{k}={v}" for k, v in counts.items()))
        if args.demo_pdfs:
            from .demo_pdfs import attach_demo_pdfs
            print(f"demo pdfs attached={attach_demo_pdfs(conn)}")
        if args.demo_usage:
            from .demo_usage import attach_demo_usage
            print(f"demo usage {attach_demo_usage(conn)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
