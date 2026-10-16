import os
from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient


_test_directory = tempfile.TemporaryDirectory(prefix="pengzhi-tests-")
_database_path = Path(_test_directory.name) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_database_path.as_posix()}"

from app.database import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database():
    from app.api.auth import _attempts
    _attempts.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        registration = test_client.post("/api/auth/register", json={
            "display_name": "测试管理员", "phone": "13900000000",
            "organization": "测试组织", "password": "Greenhouse2026",
        })
        assert registration.status_code == 200
        test_client.headers.update({"Authorization": f"Bearer {registration.json()['data']['token']}"})
        yield test_client


def pytest_sessionfinish() -> None:
    engine.dispose()
    _test_directory.cleanup()
