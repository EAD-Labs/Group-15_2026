"""Test bootstrap.

Points the app at a throwaway SQLite file and the offline `echo` provider
before `app.main` is imported, so the suite never touches a real database or
the network.
"""
import os
import tempfile

os.environ.setdefault("DEFAULT_PROVIDER", "echo")
_db_fd, _DB_PATH = tempfile.mkstemp(prefix="storystudio-test-", suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    try:
        os.remove(_DB_PATH)
    except OSError:
        pass
