import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from smartvoice import audit, auth, case_workflow, db, ui_helpers
from tests.test_case_linking import linking_db


def signed_app(call, role, path=None):
    user_id, error = auth.create_user("operator", "synthetic-password", role, "Synthetic")
    assert error is None
    app = AppTest.from_string("from smartvoice import db, ui_helpers\nimport streamlit as st\nui_helpers.render_case_link_status(db.get_call_by_id(st.session_state['call_id']), key_suffix='test')")
    if path is not None:
        app = AppTest.from_file(path, default_timeout=30)
    app.session_state["call_id"] = call
    app.session_state["current_username"] = "operator"
    app.session_state["current_user"] = "Synthetic"
    app.session_state["current_user_role"] = role
    app.session_state["current_user_id"] = user_id
    app.session_state["current_user_source"] = "db"
    return app


def prepare(call, customer, status="failed"):
    db.save_case_link_plan(call, {"action": "create", "customer_id": customer})
    if status == "failed":
        db.record_case_link_failure(call, "write_failed")


def records(call):
    return sorted([r for r in db.get_audit_log(entity=audit.ENTITY_CALL) if r["entity_id"] == call], key=lambda r: r["id"])


@pytest.mark.parametrize("role", ["Admin", "Supervisor", "Agent", "QA"])
@pytest.mark.parametrize("status", ["pending", "failed"])
def test_warning_and_retry_visibility(linking_db, role, status):
    call, customer = linking_db
    prepare(call, customer, status)
    app = signed_app(call, role).run()
    assert not app.exception
    assert any("วิเคราะห์เสียงสำเร็จ" in item.value for item in app.warning)
    assert len(app.button) == (1 if role in {"Admin", "Supervisor"} else 0)
    assert db.get_cases_by_customer(customer) == []


@pytest.mark.parametrize("role", ["Admin", "Supervisor"])
def test_button_retry_links_and_audits_without_ai(linking_db, role):
    call, customer = linking_db
    prepare(call, customer)
    app = signed_app(call, role).run()
    app.button[0].click().run()
    assert not app.exception
    assert db.get_call_by_id(call)["case_link_status"] == "linked"
    assert any("จัดเคสสำเร็จ" in item.value for item in app.success)
    assert not app.warning and not app.button
    rows = records(call)
    assert [row["changes"]["result"] for row in rows] == ["requested", "linked"]
    assert all(row["actor"] == "operator" and row["actor_role"] == role and row["created_at"] and row["action"] == audit.RETRY_CASE_LINK for row in rows)
    assert all(row["entity_label"] is None for row in rows)
    assert len(db.get_cases_by_customer(customer)) == 1


@pytest.mark.parametrize("error", ["missing_plan", "invalid_plan", "stale_plan", "customer_changed"])
def test_manual_review_has_no_retry_button(linking_db, error):
    call, customer = linking_db
    prepare(call, customer)
    with db.get_connection() as conn:
        conn.execute("UPDATE calls SET case_link_error=? WHERE id=?", (error, call))
    app = signed_app(call, "Admin").run()
    assert any("ตรวจสอบด้วยคน" in item.value for item in app.warning)
    assert not app.button
    assert db.get_cases_by_customer(customer) == []


@pytest.fixture
def session(linking_db, monkeypatch):
    call, customer = linking_db
    user_id, error = auth.create_user("operator", "synthetic-password", "Supervisor", "Synthetic")
    assert error is None
    state = {"current_username": "operator", "current_user": "Synthetic", "current_user_role": "Supervisor", "current_user_id": user_id, "current_user_source": "db"}
    fake = SimpleNamespace(session_state=state, warning=Mock(), error=Mock(), stop=lambda: pytest.fail("access denied"))
    monkeypatch.setattr(ui_helpers, "st", fake)
    prepare(call, customer)
    return call, customer, user_id


@pytest.mark.parametrize("change", ["Agent", "QA", "disabled", "deleted"])
def test_action_revalidates_and_rejects_revoked_permissions(session, monkeypatch, change):
    call, customer, user_id = session
    assert ui_helpers.get_current_user()[1] == "Supervisor"
    if change == "disabled":
        db.update_user(user_id, is_active=False)
    elif change == "deleted":
        db.delete_user(user_id)
    else:
        db.update_user(user_id, role=change)
    backend = Mock()
    monkeypatch.setattr(case_workflow, "retry_case_link", backend)
    with pytest.raises(pytest.fail.Exception, match="access denied"):
        ui_helpers.retry_case_link_for_current_user(call)
    backend.assert_not_called()
    assert db.get_cases_by_customer(customer) == []


def test_repeated_actions_use_backend_idempotency_and_log_each_result(session):
    call, customer, user_id = session
    assert ui_helpers.retry_case_link_for_current_user(call) == ("linked", True)
    assert ui_helpers.retry_case_link_for_current_user(call) == ("linked", True)
    assert len(db.get_cases_by_customer(customer)) == 1
    assert [r["changes"]["result"] for r in records(call)] == ["requested", "linked", "requested", "linked"]


def test_backend_exception_is_sanitized_and_audited(session, monkeypatch):
    call, customer, user_id = session
    monkeypatch.setattr(case_workflow, "retry_case_link", Mock(side_effect=sqlite3.OperationalError("private-secret")))
    assert ui_helpers.retry_case_link_for_current_user(call) == ("failed", True)
    assert "private-secret" not in json.dumps(records(call))
    assert records(call)[-1]["changes"] == {"result": "failed"}


def test_audit_failure_before_retry_blocks_backend(session, monkeypatch):
    call, customer, user_id = session
    backend = Mock()
    monkeypatch.setattr(case_workflow, "retry_case_link", backend)
    monkeypatch.setattr(audit, "record", Mock(return_value=None))
    assert ui_helpers.retry_case_link_for_current_user(call) == ("audit_unavailable", False)
    backend.assert_not_called()


def test_revocation_during_action_is_checked_before_backend(session, monkeypatch):
    call, customer, user_id = session
    original = audit.record
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        db.update_user(user_id, role="Agent")
        return result
    monkeypatch.setattr(audit, "record", revoke)
    backend = Mock()
    monkeypatch.setattr(case_workflow, "retry_case_link", backend)
    assert ui_helpers.retry_case_link_for_current_user(call) == ("denied", True)
    backend.assert_not_called()


def test_audit_failure_after_retry_reports_unconfirmed_audit(session, monkeypatch):
    call, customer, user_id = session
    original = audit.record
    calls = []
    def record(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs) if len(calls) == 1 else None
    monkeypatch.setattr(audit, "record", record)
    assert ui_helpers.retry_case_link_for_current_user(call) == ("linked", False)
    assert len(db.get_cases_by_customer(customer)) == 1


def test_admin_page_displays_case_link_warning(linking_db):
    call, customer = linking_db
    prepare(call, customer)
    app = signed_app(call, "Admin", "pages/1_📤_Admin.py").run()
    assert not app.exception
    assert any("วิเคราะห์เสียงสำเร็จ แต่จัดเคสไม่สำเร็จ" in item.value for item in app.warning)
    assert any(button.label == "ลองจัดเคสอีกครั้ง" for button in app.button)


def test_supervisor_links_completed_call_from_admin_page(linking_db):
    _, customer = linking_db
    call = db.insert_call("late.wav", "late-ui", "")
    db.update_call_results(call, "test", "test", "neutral", "สอบถาม")
    app = signed_app(call, "Supervisor", "pages/1_📤_Admin.py").run()
    picker = app.selectbox(key=f"cust_sel_{call}")
    picker.select(picker.options[1]).run()
    app.button(key=f"link_btn_{call}").click().run()
    assert not app.exception
    saved = db.get_call_by_id(call)
    assert saved["case_link_status"] == "linked"
    assert db.get_case_by_id(saved["case_id"])["customer_id"] == customer
    assert records(call)[-1]["changes"]["result"] == "linked"


def test_call_summaries_dialog_displays_warning_and_retries(linking_db, monkeypatch):
    call, customer = linking_db
    prepare(call, customer)
    monkeypatch.setattr(ui_helpers, "picked_row", Mock(return_value=(0, True)))
    app = signed_app(call, "Supervisor", "pages/12_Call_Summaries.py").run()
    assert not app.exception
    assert any("วิเคราะห์เสียงสำเร็จ แต่จัดเคสไม่สำเร็จ" in item.value for item in app.warning)
    next(button for button in app.button if button.label == "ลองจัดเคสอีกครั้ง").click().run()
    assert not app.exception
    assert db.get_call_by_id(call)["case_link_status"] == "linked"
    assert len(db.get_cases_by_customer(customer)) == 1


def test_failed_retry_warning_keeps_analysis_success(linking_db):
    call, customer = linking_db
    prepare(call, customer)
    with db.get_connection() as conn:
        conn.execute("CREATE TRIGGER fail_case_link BEFORE UPDATE OF case_id ON calls BEGIN SELECT RAISE(ABORT, 'private-secret'); END")
    app = signed_app(call, "Admin").run()
    app.button[0].click().run()
    assert not app.exception
    assert any("วิเคราะห์เสียงสำเร็จ" in item.value for item in app.warning)
    assert "private-secret" not in " ".join(item.value for item in app.warning)
    assert db.get_call_by_id(call)["status"] == "done"
    assert db.get_cases_by_customer(customer) == []
    assert records(call)[-1]["changes"] == {"result": "failed"}


@pytest.mark.parametrize("plan", [None, "not-json", "{}"])
def test_missing_or_invalid_plan_requires_manual_review(linking_db, plan):
    call, customer = linking_db
    with db.get_connection() as conn:
        conn.execute("UPDATE calls SET case_link_plan=? WHERE id=?", (plan, call))
    app = signed_app(call, "Admin").run()
    assert not app.exception
    assert any("ตรวจสอบด้วยคน" in item.value for item in app.warning)
    assert not app.button


def test_direct_action_cannot_bypass_manual_review(session, monkeypatch):
    call, customer, user_id = session
    with db.get_connection() as conn:
        conn.execute("UPDATE calls SET case_link_error='stale_plan' WHERE id=?", (call,))
    backend = Mock()
    monkeypatch.setattr(case_workflow, "retry_case_link", backend)
    assert ui_helpers.retry_case_link_for_current_user(call) == ("manual_review", True)
    backend.assert_not_called()
    assert records(call)[-1]["changes"] == {"result": "manual_review"}


def test_anonymous_action_is_denied(session, monkeypatch):
    call, customer, user_id = session
    ui_helpers.st.session_state.clear()
    backend = Mock()
    monkeypatch.setattr(case_workflow, "retry_case_link", backend)
    with pytest.raises(pytest.fail.Exception, match="access denied"):
        ui_helpers.retry_case_link_for_current_user(call)
    backend.assert_not_called()
