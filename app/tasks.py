import json
import os
from datetime import datetime
from pathlib import Path

from celery import Celery
from celery.schedules import crontab

from app.config import settings
from app.converter import PDFConverter, ImageConverter, CSVConverter
from app.models import TaskStatus, ConversionType, ImageFormat

celery_app = Celery(
    "file_converter",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    beat_schedule={
        "cleanup-expired-files": {
            "task": "app.tasks.cleanup_expired_files",
            "schedule": settings.cleanup_interval_hours * 3600,
        },
    },
)


def _get_redis_client():
    import redis
    return redis.from_url(settings.redis_url, decode_responses=True)


def store_task_metadata(task_id: str, metadata: dict):
    client = _get_redis_client()
    client.hset(f"task:{task_id}", mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in metadata.items()})
    client.expire(f"task:{task_id}", 86400)
    client.sadd("active_tasks", task_id)


def get_task_metadata(task_id: str) -> dict | None:
    client = _get_redis_client()
    data = client.hgetall(f"task:{task_id}")
    if not data:
        return None
    return data


def update_task_field(task_id: str, field: str, value):
    client = _get_redis_client()
    client.hset(f"task:{task_id}", field, str(value))


def get_all_task_ids() -> list[str]:
    client = _get_redis_client()
    return list(client.smembers("active_tasks"))


def remove_task_id(task_id: str):
    client = _get_redis_client()
    client.srem("active_tasks", task_id)


@celery_app.task(bind=True, name="app.tasks.convert_pdf_to_docx")
def convert_pdf_to_docx(self, task_id: str, input_path: str, output_path: str):
    try:
        update_task_field(task_id, "status", TaskStatus.PROCESSING.value)
        update_task_field(task_id, "progress", "0")

        def progress_callback(progress):
            update_task_field(task_id, "progress", str(progress))
            self.update_state(state="PROGRESS", meta={"progress": progress})

        PDFConverter.to_docx(input_path, output_path, progress_callback)

        update_task_field(task_id, "status", TaskStatus.COMPLETED.value)
        update_task_field(task_id, "progress", "100")
        update_task_field(task_id, "output_filepath", output_path)
        update_task_field(task_id, "completed_at", datetime.utcnow().isoformat())

        return {"status": "completed", "output_path": output_path}

    except Exception as e:
        update_task_field(task_id, "status", TaskStatus.FAILED.value)
        update_task_field(task_id, "error", str(e))
        update_task_field(task_id, "completed_at", datetime.utcnow().isoformat())
        raise


@celery_app.task(bind=True, name="app.tasks.convert_image")
def convert_image(
    self,
    task_id: str,
    input_path: str,
    output_path: str,
    target_format: str,
    quality: int = 85,
):
    try:
        update_task_field(task_id, "status", TaskStatus.PROCESSING.value)
        update_task_field(task_id, "progress", "0")

        def progress_callback(progress):
            update_task_field(task_id, "progress", str(progress))
            self.update_state(state="PROGRESS", meta={"progress": progress})

        fmt = ImageFormat(target_format)
        ImageConverter.convert(input_path, output_path, fmt, quality, progress_callback)

        update_task_field(task_id, "status", TaskStatus.COMPLETED.value)
        update_task_field(task_id, "progress", "100")
        update_task_field(task_id, "output_filepath", output_path)
        update_task_field(task_id, "completed_at", datetime.utcnow().isoformat())

        return {"status": "completed", "output_path": output_path}

    except Exception as e:
        update_task_field(task_id, "status", TaskStatus.FAILED.value)
        update_task_field(task_id, "error", str(e))
        update_task_field(task_id, "completed_at", datetime.utcnow().isoformat())
        raise


@celery_app.task(bind=True, name="app.tasks.convert_csv_to_json")
def convert_csv_to_json(self, task_id: str, input_path: str, output_path: str):
    try:
        update_task_field(task_id, "status", TaskStatus.PROCESSING.value)
        update_task_field(task_id, "progress", "0")

        def progress_callback(progress):
            update_task_field(task_id, "progress", str(progress))
            self.update_state(state="PROGRESS", meta={"progress": progress})

        CSVConverter.to_json(input_path, output_path, progress_callback)

        update_task_field(task_id, "status", TaskStatus.COMPLETED.value)
        update_task_field(task_id, "progress", "100")
        update_task_field(task_id, "output_filepath", output_path)
        update_task_field(task_id, "completed_at", datetime.utcnow().isoformat())

        return {"status": "completed", "output_path": output_path}

    except Exception as e:
        update_task_field(task_id, "status", TaskStatus.FAILED.value)
        update_task_field(task_id, "error", str(e))
        update_task_field(task_id, "completed_at", datetime.utcnow().isoformat())
        raise


@celery_app.task(name="app.tasks.cleanup_expired_files")
def cleanup_expired_files():
    retention_seconds = settings.file_retention_hours * 3600
    now = datetime.utcnow()
    cleaned_count = 0

    for directory in [settings.upload_path, settings.output_path]:
        if not directory.exists():
            continue
        for file_path in directory.iterdir():
            if file_path.is_file():
                file_age = (now - datetime.utcfromtimestamp(file_path.stat().st_mtime)).total_seconds()
                if file_age > retention_seconds:
                    file_path.unlink(missing_ok=True)
                    cleaned_count += 1

    task_ids = get_all_task_ids()
    for task_id in task_ids:
        metadata = get_task_metadata(task_id)
        if not metadata:
            remove_task_id(task_id)
            continue

        created_at_str = metadata.get("created_at", "")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str)
                age = (now - created_at).total_seconds()
                if age > retention_seconds:
                    client = _get_redis_client()
                    client.delete(f"task:{task_id}")
                    remove_task_id(task_id)
                    cleaned_count += 1
            except (ValueError, TypeError):
                pass

    return {"cleaned": cleaned_count}
