import os

import pytest

import db

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def migrate():
    """Build the schema the way vinted_notifications.py does at startup."""
    db.create_or_update_sqlite_db(os.path.join(REPO_ROOT, "initial_db.sql"))
    db.run_migrations(os.path.join(REPO_ROOT, "migrations"))


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    migrate()
    return db
