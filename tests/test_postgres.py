import os
import hashlib
import sqlite3
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest

from smartvoice import database_backend, db
from scripts import backup_db, migrate_postgres


@pytest.fixture
def postgres(monkeypatch):
    url = os.getenv("SMARTVOICE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("isolated PostgreSQL test database not configured")
    parsed = urlsplit(url)
    assert parsed.hostname in {"127.0.0.1", "localhost"} and parsed.path == "/smartvoice_test"
    database_backend.migrate(url)
    monkeypatch.setenv("DATABASE_URL", url)
    with database_backend.connect(url) as conn:
        conn.execute("TRUNCATE calls, customers, warranty_registrations, call_customer_links, cases, users, audit_log, sales_orders, sales_order_lines RESTART IDENTITY CASCADE")
    db.init_db()
    return url


def test_postgres_customer_warranty_and_soft_delete_contract(postgres):
    customer = db.insert_customer("Synthetic", "Customer", phone="0000000000")
    assert db.insert_customer("Other", "Name", phone="0000000000") == customer
    warranty = db.insert_warranty("TEST-WARRANTY", customer)
    db.soft_delete_customer(customer, "tester")
    assert db.get_customer_by_id(customer) is None
    db.restore_customer(customer)
    assert db.get_customer_by_id(customer)["first_name"] == "Synthetic"
    assert db.get_warranty_by_id(warranty)["customer_id"] == customer


def test_postgres_username_uniqueness_and_exception_contract(postgres):
    db.create_user("ReviewUser", "Synthetic", "Admin", "not-a-real-hash")
    assert db.get_user_by_username("reviewuser")["username"] == "ReviewUser"
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("REVIEWUSER", "Other", "Agent", "not-a-real-hash")


def test_postgres_insert_and_aggregate_contract(postgres):
    customer = db.insert_customer("Synthetic", "Customer")
    case = db.create_case(customer, "Synthetic case")
    call = db.insert_call("synthetic.wav", "synthetic-hash", "synthetic.wav")
    db.assign_call_to_case(call, case)
    assert db.get_open_cases_by_customer(customer)[0]["call_ids"] == str(call)
    assert db.count_calls_by_status()["uploaded"] == 1


def test_postgres_transaction_rollback(postgres):
    with pytest.raises(sqlite3.IntegrityError):
        with db.get_connection() as conn:
            conn.execute("INSERT INTO customers(first_name,last_name,created_at) VALUES (?,?,?)", ("Synthetic", "Rollback", "2026-01-01"))
            conn.execute("INSERT INTO customers(first_name,last_name,created_at) VALUES (?,?,?)", (None, "Invalid", "2026-01-01"))
    assert db.get_all_customers() == []


def test_postgres_case_claim_has_one_winner(postgres):
    customer = db.insert_customer("Synthetic", "Customer")
    case = db.create_case(customer, "Concurrent claim")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda n: db.claim_case(case, f"agent{n}", f"Agent {n}"), range(8)))
    assert sum(results) == 1


def test_postgres_concurrent_customer_insert_is_idempotent(postgres):
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: db.insert_customer("Synthetic", "Concurrent", phone="0000000000"), range(8)))
    assert len(set(ids)) == 1
    assert len(db.get_all_customers()) == 1


def test_postgres_concurrent_so_save_keeps_one_complete_line_set(postgres):
    def save(index):
        return db.save_sales_order({"so_number": "SO-CONCURRENT"}, [
            {"item_no": f"{index}-a", "quantity": 1},
            {"item_no": f"{index}-b", "quantity": 2},
        ])[0]
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(save, range(8)))
    assert len(set(ids)) == 1
    with db.get_connection() as conn:
        rows = conn.execute("SELECT item_no FROM sales_order_lines WHERE sales_order_id=?", (ids[0],)).fetchall()
    assert len(rows) == 2
    assert rows[0][0].split("-")[0] == rows[1][0].split("-")[0]


def test_postgres_concurrent_admin_changes_leave_one_active_admin(postgres):
    ids = [db.create_user(f"admin{n}", "Synthetic", "Admin", "not-a-real-hash") for n in range(2)]
    def disable(user_id):
        try:
            db.update_user(user_id, is_active=False)
            return True
        except db.LastAdminError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(disable, ids)) == 1
    assert db.count_active_admins() == 1


def test_sqlite_migration_preserves_ids_and_refuses_overwrite(postgres, tmp_path, monkeypatch):
    path = tmp_path / "source.db"
    with monkeypatch.context() as source_env:
        source_env.delenv("DATABASE_URL")
        source_env.setenv("DB_PATH", str(path))
        db.init_db()
        customer = db.insert_customer("Synthetic", "Migration", phone="0000000000")
        db.insert_warranty("MIGRATION-WARRANTY", customer)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert migrate_postgres.import_sqlite(path, postgres)["customers"] == 1
    assert db.get_all_customers() == []
    migrate_postgres.import_sqlite(path, postgres, apply=True)
    assert db.get_customer_by_id(customer)["last_name"] == "Migration"
    assert db.insert_customer("Next", "Customer") > customer
    with pytest.raises(ValueError, match="empty"):
        migrate_postgres.import_sqlite(path, postgres, apply=True)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_parameter_binding_keeps_literal_question_marks():
    assert database_backend.parameterized_sql("SELECT '?' AS text WHERE name LIKE ? AND note='100%' ") == "SELECT '?' AS text WHERE name ILIKE %s AND note='100%%' "


def test_postgres_backup_restores_into_new_database(postgres, tmp_path):
    customer = db.insert_customer("Synthetic", "Restore", phone="0000000000")
    snapshot = backup_db.backup_postgres(postgres, tmp_path)
    database = "smartvoice_restore_" + uuid.uuid4().hex
    restore_url = postgres.rsplit("/", 1)[0] + "/" + database
    admin = database_backend.connect(postgres)
    try:
        admin.raw.execute('CREATE DATABASE "' + database + '"')
        subprocess.run(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "--dbname", database, str(snapshot)],
                       env=backup_db.postgres_environment(restore_url), capture_output=True, check=True)
        with database_backend.connect(restore_url) as restored:
            assert restored.execute("SELECT last_name FROM customers WHERE id=?", (customer,)).fetchone()[0] == "Restore"
            assert restored.execute("SELECT version FROM smartvoice_schema_version").fetchone()[0] == database_backend.SCHEMA_VERSION
    finally:
        admin.raw.execute('DROP DATABASE IF EXISTS "' + database + '" WITH (FORCE)')
        admin.close()


def test_postgres_case_link_retry_concurrency(postgres):
    customer = db.insert_customer("Synthetic", "Customer")
    call = db.insert_call("retry.wav", "retry", "/synthetic")
    db.link_call_customer(call, customer)
    db.update_call_results(call, "synthetic", "synthetic", "neutral", "สอบถามข้อมูลสินค้า")
    db.save_case_link_plan(call, {"action": "create", "customer_id": customer})
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(db.retry_case_link, [call] * 4)) == ["linked"] * 4
    assert len(db.get_cases_by_customer(customer)) == 1
    assert db.get_call_by_id(call)["case_link_status"] == "linked"
