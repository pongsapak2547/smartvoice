import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from smartvoice import database_backend


TABLES = (
    "customers", "users", "cases", "calls", "warranty_registrations",
    "sales_orders", "sales_order_lines", "call_customer_links", "audit_log",
)


def _digest(rows):
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(list(row), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def import_sqlite(source_path, url, apply=False):
    source = sqlite3.connect(Path(source_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        source.execute("BEGIN")
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        if source.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite has foreign key violations")
        counts = {table: source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in TABLES}
        if not apply:
            return counts
        database_backend.migrate(url)
        with database_backend.connect(url) as target:
            target.raw.execute("SELECT pg_advisory_xact_lock(724613002)")
            target.raw.execute("LOCK TABLE " + ", ".join(TABLES) + " IN ACCESS EXCLUSIVE MODE")
            if any(target.raw.execute(f'SELECT EXISTS(SELECT 1 FROM "{table}")').fetchone()[0] for table in TABLES):
                raise ValueError("PostgreSQL target must be empty; existing data will not be overwritten")
            for table in TABLES:
                columns = [row[1] for row in source.execute(f'PRAGMA table_info("{table}")')]
                expected = [row[0] for row in target.raw.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position", (table,)
                )]
                if set(columns) != set(expected):
                    raise ValueError("SQLite schema differs; upgrade a copy with the matching SmartVoice version first")
                names = ", ".join('"' + name.replace('"', '""') + '"' for name in columns)
                query = f'SELECT {names} FROM "{table}" ORDER BY id'
                rows = source.execute(query)
                with target.raw.cursor() as cursor:
                    while batch := rows.fetchmany(500):
                        cursor.executemany(f'INSERT INTO "{table}" ({names}) VALUES ({", ".join(["%s"] * len(columns))})', batch)
                if _digest(source.execute(query)) != _digest(target.raw.execute(query)):
                    raise ValueError("Migration verification failed; import rolled back")
                target.raw.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM \"{table}\""
                )
        return counts
    finally:
        source.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        url = database_backend.database_url()
        if args.apply and not url:
            raise ValueError("DATABASE_URL is required")
        if args.sqlite:
            counts = import_sqlite(args.sqlite, url, args.apply)
            print(json.dumps({"applied": args.apply, "rows": counts}))
        elif args.apply:
            database_backend.migrate(url)
            print("PostgreSQL schema ready")
        else:
            print("Dry run: use --apply to initialize PostgreSQL; --sqlite reads a source database")
    except Exception as exc:
        print(f"Migration stopped ({type(exc).__name__}); source data was not modified. Check schema and target configuration.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
