"""Consistent snapshot of the SmartVoice SQLite database.

Copying the .db file while the app is writing can capture a half-written
page. This uses SQLite's online backup API from a read-only connection, checks
the copy with ``PRAGMA integrity_check`` and only then gives it its final
name, so a file named ``smartvoice-*.db`` in the backup folder is always usable.

Usage:
    python scripts/backup_db.py [--db data/smartvoice.db] [--out data/backups] [--keep 14]

Prints the path of the new snapshot. The deploy script's backup job uploads the
folder to S3; restoring is described in deploy/aws-ec2/README.md.
Snapshots hold customer data — keep them out of Git (data/ is ignored).
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

try:
    from psycopg.conninfo import conninfo_to_dict
except ImportError:
    conninfo_to_dict = None

PREFIX = "smartvoice-"
SUFFIX = ".db"


def backup(db_path: str | Path, out_dir: str | Path, now: datetime | None = None) -> Path:
    """Write a checked snapshot of ``db_path`` into ``out_dir`` and return its path."""
    source_path = Path(db_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"database not found: {source_path}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    final = out / f"{PREFIX}{stamp}{SUFFIX}"
    partial = out / f"{PREFIX}{stamp}{SUFFIX}.partial"
    partial.unlink(missing_ok=True)

    # Read-only: a backup must never be able to change the live database.
    source = sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        target = sqlite3.connect(partial)
        try:
            source.backup(target)
            result = target.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            target.close()
    finally:
        source.close()

    if result != "ok":
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"integrity check failed on the snapshot: {result}")
    os.replace(partial, final)
    return final


def prune(out_dir: str | Path, keep: int) -> list[Path]:
    """Delete the oldest snapshots beyond ``keep``; return what was removed."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    snapshots = sorted(path for path in Path(out_dir).glob(f"{PREFIX}*")
                       if re.fullmatch(r"smartvoice-\d{8}T\d{6}Z\.(db|dump)", path.name) and path.is_file())
    removed = snapshots[:-keep] if len(snapshots) > keep else []
    for path in removed:
        path.unlink()
    return removed


def postgres_environment(url: str) -> dict:
    if conninfo_to_dict is None:
        raise RuntimeError("PostgreSQL driver is not installed")
    if not url.startswith(("postgresql://", "postgres://")):
        raise ValueError("Invalid PostgreSQL URL")
    names = {
        "host": "PGHOST", "hostaddr": "PGHOSTADDR", "port": "PGPORT", "dbname": "PGDATABASE",
        "user": "PGUSER", "password": "PGPASSWORD", "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT", "sslkey": "PGSSLKEY",
        "connect_timeout": "PGCONNECT_TIMEOUT", "options": "PGOPTIONS", "application_name": "PGAPPNAME",
    }
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    try:
        options = conninfo_to_dict(url)
    except Exception:
        raise ValueError("Invalid PostgreSQL connection configuration") from None
    for key, value in options.items():
        if key not in names:
            raise ValueError("Unsupported PostgreSQL connection option for backup")
        environment[names[key]] = value
    environment.setdefault("PGCONNECT_TIMEOUT", "10")
    return environment


def backup_postgres(url: str, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final = out / f"{PREFIX}{stamp}.dump"
    partial = final.with_suffix(".dump.partial")
    if final.exists() or partial.exists():
        raise FileExistsError("Backup name already exists; retry after this backup finishes")
    environment = postgres_environment(url)
    try:
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(partial)],
                       env=environment, capture_output=True, check=True)
        subprocess.run(["pg_restore", "--list", str(partial)],
                       env=environment, capture_output=True, check=True)
        os.replace(partial, final)
    except (OSError, subprocess.CalledProcessError):
        partial.unlink(missing_ok=True)
        raise RuntimeError("PostgreSQL backup failed; check client version, connectivity and permissions") from None
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--out", default="data/backups")
    parser.add_argument("--keep", type=int, default=14, help="local snapshots to keep (default 14)")
    args = parser.parse_args(argv)
    try:
        values = dotenv_values(args.env_file)
        url = os.getenv("DATABASE_URL", values.get("DATABASE_URL") or "").strip()
        if url and not args.db:
            path = backup_postgres(url, args.out)
        else:
            args.db = args.db or os.getenv("DB_PATH") or values.get("DB_PATH") or "data/smartvoice.db"
            path = backup(args.db, args.out)
        prune(args.out, args.keep)
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
