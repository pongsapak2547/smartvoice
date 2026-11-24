import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
import requests

from smartvoice import case_workflow, database_backend, db, ollama_client, pipeline


@pytest.fixture
def linking_db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "linking.db"))
    blocked = Mock(side_effect=AssertionError("Network or AI forbidden"))
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(ollama_client, "chat", blocked)
    db.init_db()
    customer = db.insert_customer("Synthetic", "Customer")
    call = db.insert_call("synthetic.wav", "synthetic", str(tmp_path / "synthetic.wav"))
    db.link_call_customer(call, customer)
    db.update_call_results(call, "synthetic transcript", "synthetic summary", "neutral", "สอบถามข้อมูลสินค้า")
    yield call, customer
    blocked.assert_not_called()


def plan_create(call, customer):
    db.save_case_link_plan(call, {"action": "create", "customer_id": customer})


def test_create_and_repeated_retry_are_idempotent(linking_db):
    call, customer = linking_db
    plan_create(call, customer)
    assert case_workflow.retry_case_link(call) == "linked"
    first = db.get_call_by_id(call)
    assert first["status"] == "done" and first["error_msg"] is None
    assert first["case_link_error"] is None
    assert case_workflow.retry_case_link(call) == "linked"
    assert db.get_call_by_id(call) == first
    assert len(db.get_cases_by_customer(customer)) == 1
    assert json.loads(first["case_link_plan"]) == {"action": "create", "customer_id": customer}


def test_concurrent_retry_creates_one_case(linking_db):
    call, customer = linking_db
    plan_create(call, customer)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(case_workflow.retry_case_link, [call] * 4)) == ["linked"] * 4
    assert len(db.get_cases_by_customer(customer)) == 1


@pytest.mark.parametrize("stage", ["create", "link"])
def test_write_failure_rolls_back_case_and_retry_recovers(linking_db, stage):
    call, customer = linking_db
    plan_create(call, customer)
    event = "INSERT ON cases" if stage == "create" else "UPDATE OF case_id ON calls"
    with db.get_connection() as conn:
        conn.execute(f"CREATE TRIGGER fail_link BEFORE {event} BEGIN SELECT RAISE(ABORT, 'synthetic-private-secret'); END")
    assert case_workflow.retry_case_link(call) == "failed"
    failed = db.get_call_by_id(call)
    assert failed["status"] == "done" and failed["error_msg"] is None
    assert failed["case_link_status"] == "failed" and failed["case_link_error"] == "write_failed"
    assert failed["case_id"] is None and db.get_cases_by_customer(customer) == []
    with db.get_connection() as conn:
        conn.execute("DROP TRIGGER fail_link")
    assert case_workflow.retry_case_link(call) == "linked"
    assert len(db.get_cases_by_customer(customer)) == 1


def test_existing_case_and_repeated_retry(linking_db):
    call, customer = linking_db
    case = db.create_case(customer, "Synthetic")
    db.save_case_link_plan(call, {"action": "link", "customer_id": customer, "case_id": case})
    assert case_workflow.retry_case_link(call) == "linked"
    assert db.get_call_by_id(call)["case_id"] == case
    assert db.get_case_by_id(case)["status"] == "follow_up"
    assert case_workflow.retry_case_link(call) == "linked"
    assert len(db.get_cases_by_customer(customer)) == 1


@pytest.mark.parametrize("change", ["closed", "missing", "customer", "deleted_customer"])
def test_stale_plan_stops_without_new_case(linking_db, change):
    call, customer = linking_db
    case = db.create_case(customer, "Synthetic")
    db.save_case_link_plan(call, {"action": "link", "customer_id": customer, "case_id": case})
    with db.get_connection() as conn:
        if change == "closed":
            conn.execute("UPDATE cases SET status='closed' WHERE id=?", (case,))
        elif change == "missing":
            conn.execute("DELETE FROM cases WHERE id=?", (case,))
        elif change == "customer":
            conn.execute("DELETE FROM call_customer_links WHERE call_id=?", (call,))
        else:
            conn.execute("UPDATE customers SET deleted_at='synthetic' WHERE id=?", (customer,))
    assert case_workflow.retry_case_link(call) == "failed"
    saved = db.get_call_by_id(call)
    assert saved["case_id"] is None and saved["status"] == "done"
    assert saved["case_link_error"] in {"stale_plan", "customer_changed"}
    assert len(db.get_cases_by_customer(customer)) == (0 if change == "missing" else 1)


@pytest.mark.parametrize("value", [None, "not-json", '[]', '{"action":[]}', '{}', '{"action":"create","customer_id":true}', '{"action":"create","customer_id":1,"secret":"private"}'])
def test_invalid_or_missing_plan_fails_closed(linking_db, value):
    call, customer = linking_db
    with db.get_connection() as conn:
        conn.execute("UPDATE calls SET case_link_plan=? WHERE id=?", (value, call))
    assert case_workflow.retry_case_link(call) == "failed"
    assert db.get_call_by_id(call)["case_link_error"] in {"missing_plan", "invalid_plan"}
    assert db.get_cases_by_customer(customer) == []


def test_plan_cannot_be_overwritten(linking_db):
    call, customer = linking_db
    plan_create(call, customer)
    with pytest.raises(ValueError):
        db.save_case_link_plan(call, {"action": "create", "customer_id": customer, "secret": "private"})
    assert json.loads(db.get_call_by_id(call)["case_link_plan"]) == {"action": "create", "customer_id": customer}


def test_no_customer_not_required_and_unanalysed_rejected(linking_db):
    call, customer = linking_db
    other = db.insert_call("other.wav", "other", "/synthetic")
    assert db.get_call_by_id(other)["case_link_status"] is None
    with pytest.raises(ValueError, match="analysis_not_done"):
        case_workflow.retry_case_link(other)
    db.update_call_results(other, "synthetic", "synthetic", "neutral", "สอบถามข้อมูลสินค้า")
    assert case_workflow.retry_case_link(other) == "not_required"
    assert db.get_cases_by_customer(customer) == []


def test_sqlite_upgrade_backfills_once_without_creating_cases(linking_db):
    call, customer = linking_db
    case = db.create_case(customer, "Existing")
    db.assign_call_to_case(call, case)
    unlinked = db.insert_call("unlinked.wav", "unlinked", "/synthetic")
    db.link_call_customer(unlinked, customer)
    db.update_call_results(unlinked, "synthetic", "synthetic", "neutral", "สอบถามข้อมูลสินค้า")
    no_customer = db.insert_call("none.wav", "none", "/synthetic")
    db.update_call_results(no_customer, "synthetic", "synthetic", "neutral", "สอบถามข้อมูลสินค้า")
    uploaded = db.insert_call("uploaded.wav", "uploaded", "/synthetic")
    with db.get_connection() as conn:
        for column in ("case_link_status", "case_link_plan", "case_link_error", "case_link_updated_at"):
            conn.execute(f"ALTER TABLE calls DROP COLUMN {column}")
    db.init_db()
    assert [db.get_call_by_id(cid)["case_link_status"] for cid in (call, unlinked, no_customer, uploaded)] == ["linked", "pending", "not_required", None]
    assert len(db.get_cases_by_customer(customer)) == 1
    plan_create(unlinked, customer)
    assert case_workflow.retry_case_link(unlinked) == "linked"
    before = db.get_call_by_id(unlinked)
    db.init_db()
    assert db.get_call_by_id(unlinked) == before


@pytest.mark.parametrize("version", [None, 1, 2, 3])
def test_postgres_migration_runner_versions_without_database(monkeypatch, version):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.raw.execute.return_value.fetchone.return_value = None if version is None else (version,)
    monkeypatch.setattr(database_backend, "connect", Mock(return_value=connection))
    if version == 3:
        with pytest.raises(sqlite3.OperationalError):
            database_backend.migrate("synthetic")
    else:
        database_backend.migrate("synthetic")
    queries = [args.args[0] for args in connection.raw.execute.call_args_list]
    assert any("ADD COLUMN case_link_status" in q for q in queries) == (version in (None, 1))
    assert any("CREATE TABLE calls" in q for q in queries) == (version is None)


def test_pipeline_does_not_reuse_legacy_orphan(linking_db):
    call, customer = linking_db
    orphan = db.create_case(customer, "Legacy orphan")
    pipeline._auto_assign_case(call, {"topic": "สอบถามข้อมูลสินค้า", "summary": "synthetic"})
    saved = db.get_call_by_id(call)
    assert saved["case_link_status"] == "linked"
    assert saved["case_id"] != orphan
    assert db.get_calls_by_case(orphan) == []
    assert len(db.get_cases_by_customer(customer)) == 2


def test_completed_plan_cannot_recreate_a_lost_link(linking_db):
    call, customer = linking_db
    plan_create(call, customer)
    assert case_workflow.retry_case_link(call) == "linked"
    with db.get_connection() as conn:
        conn.execute("UPDATE calls SET case_id=NULL WHERE id=?", (call,))
    assert case_workflow.retry_case_link(call) == "failed"
    assert case_workflow.retry_case_link(call) == "failed"
    assert len(db.get_cases_by_customer(customer)) == 1


@pytest.mark.parametrize("existing", [False, True])
def test_late_manual_match_and_repeated_link(linking_db, existing):
    _, customer = linking_db
    call = db.insert_call("late.wav", "late", "")
    db.update_call_results(call, "test", "test", "neutral", "ติดตาม")
    assert db.auto_link_call_by_phone(call, "DEMO-MISMATCH") is None
    assert db.retry_case_link(call) == "not_required"
    db.update_customer(customer, phone="DEMO-MATCH")
    assert db.get_customer_by_phone("DEMO-MATCH")["id"] == customer
    plan = {"action": "create", "customer_id": customer}
    if existing:
        plan.update(action="link", case_id=db.create_case(customer, "Existing"))
    link = db.link_call_customer(call, customer, case_plan=plan)
    assert db.retry_case_link(call) == "linked"
    assert db.link_call_customer(call, customer, case_plan=plan) == link
    assert db.retry_case_link(call) == "linked"
    assert len(db.get_cases_by_customer(customer)) == 1
    if existing:
        assert db.get_call_by_id(call)["case_id"] == plan["case_id"]


@pytest.mark.parametrize("wrong", ["warranty", "case"])
def test_reject_cross_customer_manual_target_before_link(linking_db, wrong):
    _, customer = linking_db
    other = db.insert_customer("Other", "Demo")
    call = db.insert_call("late.wav", "late-invalid", "")
    db.update_call_results(call, "test", "test", "neutral", "ติดตาม")
    warranty = db.insert_warranty("DEMO-W", other if wrong == "warranty" else customer)
    target = db.create_case(other if wrong == "case" else customer, "Demo")
    with pytest.raises(ValueError, match="invalid_manual_case_plan"):
        db.link_call_customer(call, customer, warranty, case_plan={"action": "link", "customer_id": customer, "case_id": target})
    assert db.get_call_customer_link(call) is None
    assert db.get_call_by_id(call)["case_link_status"] == "not_required"


def test_existing_case_update_rolls_back_when_link_fails(linking_db):
    call, customer = linking_db
    case = db.create_case(customer, "Existing")
    db.save_case_link_plan(call, {"action": "link", "customer_id": customer, "case_id": case})
    before = db.get_case_by_id(case)
    with db.get_connection() as conn:
        conn.execute("CREATE TRIGGER fail_link BEFORE UPDATE OF case_id ON calls BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
    assert case_workflow.retry_case_link(call) == "failed"
    assert db.get_case_by_id(case) == before
    assert db.get_call_by_id(call)["case_id"] is None


def test_database_outage_does_not_return_linked(linking_db, monkeypatch):
    call, customer = linking_db
    plan_create(call, customer)
    with monkeypatch.context() as unavailable:
        unavailable.setattr(db, "get_connection", Mock(side_effect=sqlite3.OperationalError("synthetic-secret")))
        assert case_workflow.retry_case_link(call) == "failed"
    assert db.get_call_by_id(call)["case_link_status"] == "pending"
    assert case_workflow.retry_case_link(call) == "linked"


def test_migration_backfills_inconsistent_links_for_review(linking_db):
    call, customer = linking_db
    other = db.insert_customer("Other", "Synthetic")
    wrong_case = db.create_case(other, "Legacy orphan")
    db.assign_call_to_case(call, wrong_case)
    with db.get_connection() as conn:
        for column in ("case_link_status", "case_link_plan", "case_link_error", "case_link_updated_at"):
            conn.execute(f"ALTER TABLE calls DROP COLUMN {column}")
    db.init_db()
    assert db.get_call_by_id(call)["case_link_status"] == "pending"
    assert case_workflow.retry_case_link(call) == "failed"
    assert db.get_call_by_id(call)["case_id"] == wrong_case
    assert len(db.get_cases_by_customer(other)) == 1
    assert db.get_cases_by_customer(customer) == []


def test_late_customer_link_invalidates_not_required(linking_db):
    call, customer = linking_db
    other = db.insert_call("late.wav", "late", "/synthetic")
    db.update_call_results(other, "synthetic", "synthetic", "neutral", "สอบถามข้อมูลสินค้า")
    assert db.get_call_by_id(other)["case_link_status"] == "not_required"
    db.link_call_customer(other, customer)
    assert db.get_call_by_id(other)["case_link_status"] == "pending"
    assert case_workflow.retry_case_link(other) == "failed"
    assert db.get_call_by_id(other)["case_link_error"] == "missing_plan"
    assert db.get_cases_by_customer(customer) == []


def test_migration_failure_rolls_back_all_added_columns(linking_db):
    call, customer = linking_db
    with db.get_connection() as conn:
        for column in ("case_link_status", "case_link_plan", "case_link_error", "case_link_updated_at"):
            conn.execute(f"ALTER TABLE calls DROP COLUMN {column}")
        conn.execute("CREATE TRIGGER fail_migration BEFORE UPDATE ON calls BEGIN SELECT RAISE(ABORT, 'synthetic'); END")
    with pytest.raises(sqlite3.IntegrityError):
        db.init_db()
    with db.get_connection() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(calls)")}
        assert not any(name.startswith("case_link_") for name in columns)
        assert conn.execute("SELECT summary FROM calls WHERE id=?", (call,)).fetchone()[0] == "synthetic summary"
        conn.execute("DROP TRIGGER fail_migration")
    db.init_db()
    assert db.get_call_by_id(call)["case_link_status"] == "pending"
    assert db.get_cases_by_customer(customer) == []


def test_planning_failure_stays_done_and_retry_never_replans(linking_db, monkeypatch):
    call, customer = linking_db
    old_case = db.create_case(customer, "Existing")
    old_call = db.insert_call("old.wav", "old", "/synthetic")
    db.assign_call_to_case(old_call, old_case)
    monkeypatch.setattr(pipeline, "CASE_RECENCY_HOURS", 0)
    match = Mock(side_effect=ollama_client.APIError("synthetic-private-secret"))
    monkeypatch.setattr(ollama_client, "match_case", match)
    pipeline._auto_assign_case(call, {"topic": "สอบถามข้อมูลสินค้า", "summary": "synthetic"})
    saved = db.get_call_by_id(call)
    assert saved["status"] == "done" and saved["error_msg"] is None
    assert saved["case_link_status"] == "failed"
    assert saved["case_link_error"] == "planning_failed"
    assert saved["case_link_plan"] is None
    assert case_workflow.retry_case_link(call) == "failed"
    pipeline._auto_assign_case(call, {"topic": "สอบถามข้อมูลสินค้า", "summary": "synthetic"})
    match.assert_called_once()
    assert len(db.get_cases_by_customer(customer)) == 1


def test_saved_plan_is_not_replaced_by_another_valid_plan(linking_db):
    call, customer = linking_db
    plan_create(call, customer)
    case = db.create_case(customer, "Other")
    db.save_case_link_plan(call, {"action": "link", "customer_id": customer, "case_id": case})
    assert json.loads(db.get_call_by_id(call)["case_link_plan"]) == {"action": "create", "customer_id": customer}


def test_schema_rejects_unknown_link_status(linking_db):
    call, customer = linking_db
    with pytest.raises(sqlite3.IntegrityError):
        with db.get_connection() as conn:
            conn.execute("UPDATE calls SET case_link_status='unknown' WHERE id=?", (call,))
    assert db.get_call_by_id(call)["case_link_status"] == "pending"


def test_postgres_runner_does_not_advance_version_after_migration_failure(monkeypatch):
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)

    def execute(sql, *args):
        if "ADD COLUMN case_link_status" in sql:
            raise sqlite3.OperationalError("synthetic migration failure")
        result = Mock()
        result.fetchone.return_value = (1,)
        return result

    connection.raw.execute.side_effect = execute
    monkeypatch.setattr(database_backend, "connect", Mock(return_value=connection))
    with pytest.raises(sqlite3.OperationalError):
        database_backend.migrate("synthetic")
    assert not any("UPDATE smartvoice_schema_version" in call.args[0] for call in connection.raw.execute.call_args_list)
    assert connection.__exit__.call_args.args[0] is sqlite3.OperationalError
