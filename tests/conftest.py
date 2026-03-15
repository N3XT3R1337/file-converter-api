import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings


@pytest.fixture(scope="session")
def temp_dirs():
    upload_dir = tempfile.mkdtemp(prefix="test_uploads_")
    output_dir = tempfile.mkdtemp(prefix="test_outputs_")
    yield upload_dir, output_dir
    shutil.rmtree(upload_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def mock_settings(temp_dirs):
    upload_dir, output_dir = temp_dirs
    test_settings = Settings(
        redis_url="redis://localhost:6379/15",
        upload_dir=upload_dir,
        output_dir=output_dir,
        max_upload_size_mb=10,
        cleanup_interval_hours=1,
        file_retention_hours=24,
    )
    with patch("app.config.settings", test_settings):
        with patch("app.routes.settings", test_settings):
            with patch("app.tasks.settings", test_settings):
                with patch("app.scheduler.settings", test_settings):
                    yield test_settings


@pytest.fixture
def mock_redis():
    storage = {}
    sets_storage = {}

    class MockRedis:
        def __init__(self, *args, **kwargs):
            pass

        def hset(self, key, field=None, value=None, mapping=None):
            if key not in storage:
                storage[key] = {}
            if mapping:
                storage[key].update(mapping)
            elif field and value:
                storage[key][field] = value

        def hgetall(self, key):
            return storage.get(key, {})

        def expire(self, key, seconds):
            pass

        def sadd(self, key, *values):
            if key not in sets_storage:
                sets_storage[key] = set()
            sets_storage[key].update(values)

        def smembers(self, key):
            return sets_storage.get(key, set())

        def srem(self, key, *values):
            if key in sets_storage:
                sets_storage[key] -= set(values)

        def delete(self, key):
            storage.pop(key, None)

        def ping(self):
            return True

        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

    with patch("app.tasks._get_redis_client", return_value=MockRedis()):
        with patch("app.routes.get_task_metadata") as mock_get:
            with patch("app.routes.store_task_metadata") as mock_store:
                with patch("app.routes.get_all_task_ids") as mock_list:
                    mock_list.return_value = []
                    yield {
                        "get": mock_get,
                        "store": mock_store,
                        "list": mock_list,
                        "storage": storage,
                        "sets": sets_storage,
                    }


@pytest.fixture
def mock_celery_tasks():
    with patch("app.routes.convert_pdf_to_docx") as mock_pdf:
        with patch("app.routes.convert_image") as mock_img:
            with patch("app.routes.convert_csv_to_json") as mock_csv:
                mock_pdf.delay = MagicMock()
                mock_img.delay = MagicMock()
                mock_csv.delay = MagicMock()
                yield {
                    "pdf": mock_pdf,
                    "image": mock_img,
                    "csv": mock_csv,
                }


@pytest.fixture
def client(mock_redis, mock_celery_tasks):
    with patch("app.main.cleanup_scheduler"):
        from app.main import app
        with TestClient(app) as c:
            yield c


@pytest.fixture
def sample_csv(temp_dirs):
    upload_dir, _ = temp_dirs
    csv_path = Path(upload_dir) / "test.csv"
    csv_path.write_text("name,age,active\nAlice,30,true\nBob,25,false\n", encoding="utf-8")
    return str(csv_path)


@pytest.fixture
def sample_image(temp_dirs):
    from PIL import Image
    upload_dir, _ = temp_dirs
    img_path = Path(upload_dir) / "test.png"
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(str(img_path))
    img.close()
    return str(img_path)
