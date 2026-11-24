import json
import sqlite3
import sys

import pytest

from smartvoice import db
from scripts import backfill_topic_detail, scrub_existing_next_actions
from tests.test_postgres import postgres


@pytest.fixture(params=["sqlite", "postgres"])
def script_database(request, monkeypatch, tmp_path):
    if request.param == "postgres":
        request.getfixturevalue("postgres")
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_PATH", str(tmp_path / "scripts.db"))
        db.init_db()
    for index in range(2):
        call = db.insert_call(f"synthetic-{index}.wav", f"hash-{index}", "synthetic.wav")
        with db.get_connection() as conn:
            conn.execute("UPDATE calls SET status='done', transcript=?, topic=?, agent_performance=? WHERE id=?",
                         ("synthetic transcript", backfill_topic_detail.PRODUCT_ISSUE_TOPIC,
                          json.dumps({"next_action": "old"}), call))


@pytest.mark.parametrize("script", [backfill_topic_detail, scrub_existing_next_actions])
@pytest.mark.parametrize("mode", ["success", "failure", "dry_run"])
def test_script_updates_are_atomic(script_database, script, mode, monkeypatch):
    monkeypatch.setattr(backfill_topic_detail, "_classify", lambda _: "อื่นๆ")
    monkeypatch.setattr(scrub_existing_next_actions, "_scrub_prompt_example_leakage", lambda *_: "new")
    monkeypatch.setattr(sys, "argv", ["script"] + ([] if mode == "dry_run" else ["--apply"]))
    original = db.get_connection

    class FailingConnection:
        def __init__(self):
            self.inner = original()
            self.writes = 0

        def execute(self, query, args=()):
            if query.lstrip().startswith("UPDATE"):
                self.writes += 1
                if self.writes == 2:
                    raise sqlite3.OperationalError("synthetic second-write failure")
            return self.inner.execute(query, args)

        def __enter__(self):
            self.inner.__enter__()
            return self

        def __exit__(self, *args):
            return self.inner.__exit__(*args)

        def close(self):
            self.inner.close()

    if mode == "failure":
        with monkeypatch.context() as patch:
            patch.setattr(db, "get_connection", FailingConnection)
            with pytest.raises(sqlite3.OperationalError, match="second-write"):
                script.main()
    else:
        assert script.main() == 0
    with original() as conn:
        rows = conn.execute("SELECT topic_detail, agent_performance FROM calls ORDER BY id").fetchall()
    for row in rows:
        if script is backfill_topic_detail:
            assert row["topic_detail"] == ("อื่นๆ" if mode == "success" else None)
        else:
            assert json.loads(row["agent_performance"])["next_action"] == ("new" if mode == "success" else "old")
