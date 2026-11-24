"""The login page: server-wide lockout and never printing an operator's password."""

from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from smartvoice import auth, db, login_guard, ui_helpers


def _login_script():
    from smartvoice import ui_helpers

    ui_helpers.render_login_page()


@pytest.fixture
def login_env(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SMARTVOICE_USERS", "")
    monkeypatch.delenv(auth.BOOTSTRAP_PASSWORD_ENV, raising=False)
    db.init_db()
    user_id, error = auth.create_user("somchai", "correct-horse", "Agent", "Somchai")
    assert user_id and error is None
    login_guard.clear_all()
    yield
    login_guard.clear_all()


def _attempt(at: AppTest, username: str, password: str) -> AppTest:
    at.text_input(key="_login_username").input(username)
    at.text_input(key="_login_password").input(password)
    at.button[0].click()
    return at.run()


def _errors(at: AppTest) -> str:
    return " ".join(e.value for e in at.error)


def test_lock_survives_a_new_browser_session(login_env):
    first = AppTest.from_function(_login_script, default_timeout=30).run()
    for _ in range(login_guard.ACCOUNT_MAX_FAILURES):
        first = _attempt(first, "somchai", "wrong-password")
    assert "ถูกล็อก" in _errors(first)

    # A fresh AppTest is a separate Streamlit session — the old session_state
    # lockout reset here; the right password must still be refused.
    second = AppTest.from_function(_login_script, default_timeout=30).run()
    second = _attempt(second, "SOMCHAI", "correct-horse")

    assert "ถูกล็อก" in _errors(second)
    assert "current_user" not in second.session_state


def test_successful_login_clears_the_account_counter(login_env):
    at = AppTest.from_function(_login_script, default_timeout=30).run()
    _attempt(at, "somchai", "wrong-password")
    assert login_guard.failures_left(login_guard.account_key("somchai"), 5) == 4

    _attempt(at, "somchai", "correct-horse")

    assert login_guard.failures_left(login_guard.account_key("somchai"), 5) == 5


def test_published_default_is_shown_without_an_operator_password(monkeypatch, tmp_path):
    """Local behaviour is unchanged: the first-run hint still names admin1234."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SMARTVOICE_USERS", "")
    monkeypatch.delenv(auth.BOOTSTRAP_PASSWORD_ENV, raising=False)
    db.init_db()
    assert auth.ensure_default_admin() is True

    at = AppTest.from_function(_login_script, default_timeout=30).run()
    assert any(auth.DEFAULT_ADMIN_PASSWORD in i.value for i in at.info)


def test_operator_bootstrap_password_is_never_printed(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SMARTVOICE_USERS", "")
    monkeypatch.setenv(auth.BOOTSTRAP_PASSWORD_ENV, "server-only-secret")
    db.init_db()
    assert auth.ensure_default_admin() is True

    at = AppTest.from_function(_login_script, default_timeout=30).run()
    shown = " ".join(i.value for i in at.info)

    assert "server-only-secret" not in shown
    assert auth.DEFAULT_ADMIN_PASSWORD not in shown
    assert auth.DEFAULT_ADMIN_USERNAME in shown


@pytest.mark.parametrize(
    ("peer", "forwarded", "expected"),
    [
        ("203.0.113.9", "", "203.0.113.9"),             # direct connection
        ("203.0.113.9", "198.51.100.1", "203.0.113.9"),  # header ignored when direct
        (None, "", None),                                # local use
        ("127.0.0.1", "198.51.100.7", "198.51.100.7"),   # behind the local proxy
        ("127.0.0.1", "10.0.0.1, 198.51.100.7", "198.51.100.7"),  # spoofed first hop ignored
        ("::1", "", None),
    ],
)
def test_client_address(monkeypatch, peer, forwarded, expected):
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    fake = SimpleNamespace(context=SimpleNamespace(ip_address=peer, headers=headers))
    monkeypatch.setattr(ui_helpers, "st", fake)

    assert ui_helpers._client_address() == expected


@pytest.fixture
def session_env(login_env, monkeypatch):
    state = {}
    fake = SimpleNamespace(
        session_state=state,
        warning=lambda message: None,
        error=lambda message: None,
        stop=lambda: pytest.fail("access denied"),
    )
    monkeypatch.setattr(ui_helpers, "st", fake)
    monkeypatch.setattr(ui_helpers.audit_trail, "record", lambda *args, **kwargs: None)
    return state


def test_demoted_admin_loses_navigation_and_page_access(session_env, monkeypatch):
    state = session_env
    auth.create_user("keeper", "keeper-password", "Admin")
    user_id, _ = auth.create_user("admin2", "staff-password", "Admin")
    ui_helpers.start_session(auth.authenticate("admin2", "staff-password"))
    assert ui_helpers.require_page(auth.PAGE_USERS)[1] == "Admin"
    db.update_user(user_id, role="Agent")
    user, role = ui_helpers.get_current_user()
    assert role == "Agent"
    assert auth.PAGE_USERS not in auth.visible_pages(role)
    with pytest.raises(pytest.fail.Exception, match="access denied"):
        ui_helpers.require_page(auth.PAGE_USERS)
    assert state["current_user_role"] == "Agent"


@pytest.mark.parametrize("operation", ["disable", "delete"])
def test_account_revocation_clears_session(session_env, monkeypatch, operation):
    state = session_env
    record = auth.authenticate("somchai", "correct-horse")
    monkeypatch.setenv("SMARTVOICE_USERS", f"somchai|Admin|{record.password_hash}")
    ui_helpers.start_session(record)
    assert ui_helpers.get_current_user() == ("Somchai", "Agent")
    if operation == "disable":
        db.update_user(record.user_id, is_active=False)
    else:
        db.delete_user(record.user_id)
    assert ui_helpers.get_current_user() == (None, None)
    assert all(key not in state for key in ui_helpers._SESSION_KEYS)
    with pytest.raises(pytest.fail.Exception, match="access denied"):
        ui_helpers.require_page(auth.PAGE_DASHBOARD)


def test_session_database_failure_is_fail_closed(session_env, monkeypatch):
    state = session_env
    ui_helpers.start_session(auth.authenticate("somchai", "correct-horse"))
    ui_helpers.get_current_user()

    def unavailable(user_id):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db, "get_user_by_id", unavailable)
    assert ui_helpers.get_current_user() == (None, None)
    assert "current_user_role" not in state


def test_page_guard_rechecks_account_after_navigation_lookup(session_env):
    auth.create_user("keeper", "keeper-password", "Admin")
    user_id, _ = auth.create_user("admin2", "staff-password", "Admin")
    ui_helpers.start_session(auth.authenticate("admin2", "staff-password"))
    user, role = ui_helpers.get_current_user()
    assert auth.PAGE_USERS in auth.visible_pages(role)
    db.update_user(user_id, role="Agent")
    with pytest.raises(pytest.fail.Exception, match="access denied"):
        ui_helpers.require_page(auth.PAGE_USERS)
    assert session_env["current_user_role"] == "Agent"
    db.update_user(user_id, is_active=False)
    assert ui_helpers.get_current_user_id() is None
    assert ui_helpers.get_current_user() == (None, None)


def test_two_sessions_and_logout_are_isolated(session_env, monkeypatch):
    first = session_env
    auth.create_user("second", "second-password", "QA")
    ui_helpers.start_session(auth.authenticate("somchai", "correct-horse"))
    assert ui_helpers.get_current_user() == ("Somchai", "Agent")
    second = {}
    monkeypatch.setattr(ui_helpers.st, "session_state", second)
    ui_helpers.start_session(auth.authenticate("second", "second-password"))
    assert ui_helpers.get_current_user() == ("second", "QA")
    ui_helpers.end_session()
    assert ui_helpers.get_current_user() == (None, None)
    monkeypatch.setattr(ui_helpers.st, "session_state", first)
    assert ui_helpers.get_current_user() == ("Somchai", "Agent")
    ui_helpers.end_session()
    ui_helpers.start_session(auth.authenticate("second", "second-password"))
    assert ui_helpers.get_current_user() == ("second", "QA")


def test_env_session_is_revoked_when_database_account_appears(session_env, monkeypatch):
    state = session_env
    encoded = auth.hash_password("env-password")
    monkeypatch.setenv("SMARTVOICE_USERS", f"fallback|Admin|{encoded}")
    ui_helpers.start_session(auth.authenticate("fallback", "env-password"))
    assert ui_helpers.get_current_user() == ("fallback", "Admin")
    db.create_user("fallback", "Fallback", "Agent", encoded, is_active=False)
    assert ui_helpers.get_current_user() == (None, None)

def test_real_streamlit_rerun_revalidates_before_navigation(login_env):
    auth.create_user("keeper", "keeper-password", "Admin")
    user_id, _ = auth.create_user("admin2", "staff-password", "Admin")
    script = """
import streamlit as st
from smartvoice import auth, ui_helpers

if st.button("Login"):
    ui_helpers.start_session(auth.authenticate("admin2", "staff-password"))
user, role = ui_helpers.get_current_user()
st.write(auth.visible_pages(role) if user else [])
if user:
    ui_helpers.require_page(auth.PAGE_USERS)
    st.success("admin access")
"""
    at = AppTest.from_string(script, default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.success[0].value == "admin access"
    db.update_user(user_id, role="Agent")
    at.run()
    assert not at.exception
    assert not at.success
    assert at.error
    assert at.session_state["current_user_role"] == "Agent"
    db.update_user(user_id, is_active=False)
    at.run()
    assert not at.exception
    assert "current_user" not in at.session_state
