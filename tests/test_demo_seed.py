import os
import secrets
import sqlite3
import subprocess
import sys
from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from smartvoice import auth, dashboard_report, db


def test_isolated_demo_seed_reset_and_roles(tmp_path, monkeypatch):
    directory = tmp_path / "smartvoice-demo"
    target = directory / "demo.sqlite3"
    password = secrets.token_urlsafe(16)
    env = dict(os.environ, DATABASE_URL="postgresql://unused.invalid/unused", SMARTVOICE_DEMO_PASSWORD=password)
    command = [sys.executable, str(Path("scripts/seed_mock_data.py").resolve()), "--demo-dir", str(directory)]
    for args in ([], [], ["--reset"]):
        subprocess.run(command + args, env=env, check=True, capture_output=True)
        monkeypatch.setenv("DATABASE_URL", "")
        monkeypatch.setenv("DB_PATH", str(target))
        assert db.count_users() == 4
        for role in auth.ROLES:
            assert auth.authenticate("demo_" + role.lower(), password).role == role
        calls = db.get_done_calls()
        assert dashboard_report.build_report(calls).total == 3
        assert len({c["case_id"] for c in calls}) == 2
        for call in calls:
            link = db.get_call_customer_link(call["id"])
            warranty = db.get_warranty_by_id(link["warranty_id"])
            order = db.get_sales_order(so_number=warranty["so_number"])
            assert order["customer_id"] == link["customer_id"] == db.get_case_by_id(call["case_id"])["customer_id"]
            assert order["lines"]
    unrelated = tmp_path / "other" / "smartvoice-demo"
    unrelated.mkdir(parents=True)
    with sqlite3.connect(unrelated / "demo.sqlite3") as conn:
        conn.execute("CREATE TABLE keep_me(id integer)")
    assert subprocess.run(command[:-1] + [str(unrelated), "--reset"], env=env, capture_output=True).returncode
    with sqlite3.connect(unrelated / "demo.sqlite3") as conn:
        assert conn.execute("SELECT * FROM keep_me").fetchall() == []
    root = Path.cwd()
    monkeypatch.chdir(directory)
    navigate = st.navigation
    pages = {}
    selected = []

    def track_navigation(groups, **kwargs):
        page = navigate(groups, **kwargs)
        if isinstance(groups, dict):
            pages.update({p._script_hash: p.title for group in groups.values() for p in group})
        selected.append(page._script_hash)
        return page

    monkeypatch.setattr(st, "navigation", track_navigation)
    for role in auth.ROLES:
        pages.clear()
        app = AppTest.from_file(str(root / "Home.py"), default_timeout=30).run()
        app.text_input(key="_login_username").input("demo_" + role.lower())
        app.text_input(key="_login_password").input(password)
        app.button[0].click().run()
        assert not app.exception and app.session_state["current_user_role"] == role
        assert len(pages) == len(auth.visible_pages(role))
        if role == "Admin":
            for page_hash, title in list(pages.items()):
                app._page_hash = page_hash
                app.run()
                assert not app.exception and selected[-1] == page_hash, title
        app.button(key="_logout_btn").click().run()
        assert not app.exception and "current_username" not in app.session_state
