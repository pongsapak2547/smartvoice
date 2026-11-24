import os
import re
import sqlite3
from pathlib import Path

try:
    import psycopg
except ImportError:
    psycopg = None


SCHEMA_VERSION = 2
_SQL_LITERAL = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*.*?\*/)", re.S)


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if value and not value.startswith(("postgresql://", "postgres://")):
        raise sqlite3.OperationalError("DATABASE_URL must use PostgreSQL")
    return value


def parameterized_sql(query: str) -> str:
    chunks = _SQL_LITERAL.split(query)
    for index, chunk in enumerate(chunks):
        chunk = chunk.replace("%", "%%")
        if index % 2 == 0:
            chunk = chunk.replace("?", "%s")
            chunk = re.sub(r"\bLIKE\b", "ILIKE", chunk, flags=re.I)
        chunks[index] = chunk
    return "".join(chunks)


class _Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    def __init__(self, cursor, inserted=False):
        self.rowcount = cursor.rowcount
        self.lastrowid = cursor.fetchone()[0] if inserted else None
        self._cursor = cursor

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _Row(zip((column.name for column in self._cursor.description), row))

    def fetchall(self):
        columns = [column.name for column in self._cursor.description]
        return [_Row(zip(columns, row)) for row in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    def __init__(self, connection):
        self.raw = connection
        self._transaction = None

    def execute(self, query, parameters=()):
        inserted = bool(re.match(r"\s*INSERT\s+INTO\b", query, re.I))
        if inserted:
            query = query.rstrip().rstrip(";") + " RETURNING id"
        try:
            cursor = self.raw.execute(parameterized_sql(query), tuple(parameters))
            return _Cursor(cursor, inserted)
        except psycopg.IntegrityError:
            if self._transaction is None:
                self.close()
            raise sqlite3.IntegrityError("Database constraint violation") from None
        except psycopg.Error:
            if self._transaction is None:
                self.close()
            raise sqlite3.OperationalError("PostgreSQL operation failed") from None

    def __enter__(self):
        self._transaction = self.raw.transaction()
        self._transaction.__enter__()
        return self

    def __exit__(self, kind, value, traceback):
        try:
            return self._transaction.__exit__(kind, value, traceback)
        except psycopg.Error:
            raise sqlite3.OperationalError("PostgreSQL transaction failed") from None
        finally:
            self._transaction = None
            self.close()

    def close(self):
        self.raw.close()


def connect(url=None):
    if psycopg is None:
        raise sqlite3.OperationalError("Install psycopg[binary] to use PostgreSQL")
    try:
        connection = psycopg.connect(url or database_url(), autocommit=True, connect_timeout=10)
        connection.execute("SET statement_timeout = '60s'")
        connection.execute("SET lock_timeout = '10s'")
        return Connection(connection)
    except psycopg.Error:
        raise sqlite3.OperationalError("PostgreSQL connection failed; check server configuration") from None


def check_schema():
    with connect() as connection:
        row = connection.execute("SELECT version FROM smartvoice_schema_version").fetchone()
        if not row or row[0] != SCHEMA_VERSION:
            raise sqlite3.OperationalError("Run the PostgreSQL schema migration before starting SmartVoice")


def migrate(url=None):
    with connect(url) as connection:
        connection.raw.execute("SELECT pg_advisory_xact_lock(724613001)")
        connection.raw.execute("CREATE TABLE IF NOT EXISTS smartvoice_schema_version (version INTEGER PRIMARY KEY)")
        row = connection.raw.execute("SELECT version FROM smartvoice_schema_version").fetchone()
        version = row[0] if row else 0
        if version not in (0, 1, SCHEMA_VERSION):
            raise sqlite3.OperationalError("Unsupported PostgreSQL schema version")
        directory = Path(__file__).resolve().parent.parent / "migrations"
        if version == 0:
            connection.raw.execute((directory / "001_postgresql.sql").read_text(encoding="utf-8"))
        if version < 2:
            connection.raw.execute((directory / "002_case_linking.sql").read_text(encoding="utf-8"))
            if row:
                connection.raw.execute("UPDATE smartvoice_schema_version SET version = %s", (SCHEMA_VERSION,))
            else:
                connection.raw.execute("INSERT INTO smartvoice_schema_version VALUES (%s)", (SCHEMA_VERSION,))
