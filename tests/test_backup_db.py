"""scripts/backup_db.py — consistent, checked SQLite snapshots."""

import importlib.util
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from smartvoice import db

_SPEC = importlib.util.spec_from_file_location(
    "backup_db", Path(__file__).resolve().parent.parent / "scripts" / "backup_db.py"
)
backup_db = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(backup_db)


@pytest.fixture
def live_db(monkeypatch, tmp_path):
    path = tmp_path / "live" / "smartvoice.db"
    monkeypatch.setenv("DB_PATH", str(path))
    db.init_db()
    db.insert_customer("สมชาย", "ใจดี", phone="0800000001")
    return path


def test_snapshot_contains_the_data_and_passes_integrity_check(live_db, tmp_path):
    snap = backup_db.backup(live_db, tmp_path / "backups",
                            now=datetime(2026, 11, 15, 9, 30, tzinfo=timezone.utc))

    assert snap.name == "smartvoice-20261115T093000Z.db"
    with sqlite3.connect(snap) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT phone FROM customers").fetchall() == [("0800000001",)]
    assert not list((tmp_path / "backups").glob("*.partial"))


def test_snapshot_works_while_a_writer_holds_the_database(live_db, tmp_path):
    writer = sqlite3.connect(live_db)
    writer.execute("BEGIN")
    writer.execute("UPDATE customers SET nick_name = 'ยังไม่ commit'")
    try:
        snap = backup_db.backup(live_db, tmp_path / "backups")
    finally:
        writer.rollback()
        writer.close()

    with sqlite3.connect(snap) as conn:
        # The uncommitted change is not in the snapshot.
        assert conn.execute("SELECT nick_name FROM customers").fetchone()[0] is None


def test_backup_never_writes_the_live_database(live_db, tmp_path):
    before = live_db.read_bytes()
    backup_db.backup(live_db, tmp_path / "backups")

    assert live_db.read_bytes() == before


def test_missing_database_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup_db.backup(tmp_path / "nope.db", tmp_path / "backups")
    assert backup_db.main(["--db", str(tmp_path / "nope.db"), "--out", str(tmp_path / "b")]) == 1


def test_prune_keeps_the_newest(tmp_path):
    for day in range(1, 6):
        (tmp_path / f"smartvoice-202611{day:02d}T000000Z.db").write_bytes(b"x")
    (tmp_path / "unrelated.db").write_bytes(b"x")

    removed = backup_db.prune(tmp_path, keep=2)

    assert [p.name for p in removed] == [
        "smartvoice-20261101T000000Z.db", "smartvoice-20261102T000000Z.db",
        "smartvoice-20261103T000000Z.db",
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "smartvoice-20261104T000000Z.db", "smartvoice-20261105T000000Z.db", "unrelated.db",
    ]
    with pytest.raises(ValueError):
        backup_db.prune(tmp_path, keep=0)


def test_main_prints_the_snapshot_path(live_db, tmp_path, capsys):
    assert backup_db.main(["--db", str(live_db), "--out", str(tmp_path / "b"), "--keep", "3"]) == 0
    printed = Path(capsys.readouterr().out.strip())
    assert printed.is_file()


def test_prune_preserves_manual_backups(tmp_path):
    names = ["smartvoice-000-manual.db", "smartvoice-20261101T000000Z.db", "smartvoice-20261102T000000Z.db"]
    for name in names:
        (tmp_path / name).write_bytes(b"synthetic")
    backup_db.prune(tmp_path, 1)
    assert (tmp_path / names[0]).is_file()


def test_main_reads_db_path_from_env_file(live_db, tmp_path, monkeypatch, capsys):
    env_file = tmp_path / "backup-test.env"
    env_file.write_text(f"DB_PATH='{live_db.as_posix()}'\n", encoding="utf-8")
    monkeypatch.delenv("DB_PATH")
    assert backup_db.main(["--env-file", str(env_file), "--out", str(tmp_path / "backup")]) == 0
    snapshot = Path(capsys.readouterr().out.strip())
    with sqlite3.connect(snapshot) as conn:
        assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1


def test_invalid_postgres_configuration_never_prints_credentials(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:synthetic-secret@host/db?unknown_option=synthetic-secret")
    assert backup_db.main(["--out", str(tmp_path)]) == 1
    assert "synthetic-secret" not in capsys.readouterr().err
