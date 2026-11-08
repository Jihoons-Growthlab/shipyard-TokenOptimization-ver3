"""SQLite 연결·트랜잭션·마이그레이션."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or config.db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    """쓰기 트랜잭션(BEGIN IMMEDIATE)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def migrate(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for f in sorted(config.MIGRATIONS_DIR.glob("[0-9]*_*.sql")):
        version = f.name.split("_", 1)[0]
        if version in done:
            continue
        with tx(conn):
            for stmt in _split_sql(f.read_text(encoding="utf-8")):
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        applied.append(version)
    return applied


def _split_sql(script: str) -> list[str]:
    out, buf = [], ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows(conn, sql: str, *args) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, args)]


def one(conn, sql: str, *args) -> dict | None:
    r = conn.execute(sql, args).fetchone()
    return dict(r) if r else None


def scalar(conn, sql: str, *args):
    r = conn.execute(sql, args).fetchone()
    return r[0] if r else None
