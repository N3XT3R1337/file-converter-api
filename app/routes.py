import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import settings
from app.converter import ConverterFactory, ImageConverter
from app.models import (
    ConversionType,
    ImageFormat,
    TaskResponse,
    TaskStatus,
    TaskStatusResponse,
    TaskListResponse,
    TaskListItem,
    HealthResponse,
    ErrorResponse,
)
from app.tasks import (
    convert_pdf_to_docx,
    convert_image,
    convert_csv_to_json,
    store_task_metadata,
    get_task_metadata,
    get_all_task_ids,
)

router = APIRouter(prefix="/api/v1")
health_router = APIRouter()


@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    redis_status = "disconnected"
    try:
        import redis
        client = redis.from_url(settings.redis_url)
        client.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return HealthResponse(
        status="healthy" if redis_status == "connected" else "degraded",
        redis=redis_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
        version=settings.app_version,
    )


async def _save_upload(file: UploadFile, task_id: str) -> tuple[str, int]:
    content = await file.read()
    file_size = len(content)

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed size of {settings.max_upload_size_mb}MB",
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    ext = Path(file.filename).suffix if file.filename else ""
    safe_filename = f"{task_id}{ext}"
    file_path = settings.upload_path / safe_filename

    with open(file_path, "wb") as f:
        f.write(content)

    return str(file_path), file_size


@router.post(
    "/convert/pdf-to-docx",
    response_model=TaskResponse,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def convert_pdf_to_docx_endpoint(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    task_id = str(uuid.uuid4())
    file_path, file_size = await _save_upload(file, task_id)
    output_path = str(settings.output_path / f"{task_id}.docx")

    metadata = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "progress": "0",
        "conversion_type": ConversionType.PDF_TO_DOCX.value,
        "original_filename": file.filename,
        "original_filepath": file_path,
        "output_filepath": output_path,
        "created_at": datetime.utcnow().isoformat(),
        "file_size": str(file_size),
    }
    store_task_metadata(task_id, metadata)

    convert_pdf_to_docx.delay(task_id, file_path, output_path)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="PDF to DOCX conversion task queued",
    )


@router.post(
    "/convert/image",
    response_model=TaskResponse,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def convert_image_endpoint(
    file: UploadFile = File(...),
    target_format: ImageFormat = Form(...),
    quality: int = Form(default=85, ge=1, le=100),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    source_format = ImageConverter.get_format_from_extension(file.filename)
    if source_format is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Supported: PNG, JPEG, WEBP, BMP, TIFF, GIF",
        )

    if source_format == target_format:
        raise HTTPException(
            status_code=400,
            detail="Source and target formats are the same",
        )

    task_id = str(uuid.uuid4())
    file_path, file_size = await _save_upload(file, task_id)

    out_ext = ImageConverter.get_extension(target_format)
    output_path = str(settings.output_path / f"{task_id}{out_ext}")

    metadata = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "progress": "0",
        "conversion_type": ConversionType.IMAGE_CONVERT.value,
        "original_filename": file.filename,
        "original_filepath": file_path,
        "output_filepath": output_path,
        "created_at": datetime.utcnow().isoformat(),
        "file_size": str(file_size),
        "target_format": target_format.value,
        "quality": str(quality),
    }
    store_task_metadata(task_id, metadata)

    convert_image.delay(task_id, file_path, output_path, target_format.value, quality)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Image conversion task queued",
    )


@router.post(
    "/convert/csv-to-json",
    response_model=TaskResponse,
    responses={400: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def convert_csv_to_json_endpoint(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    task_id = str(uuid.uuid4())
    file_path, file_size = await _save_upload(file, task_id)
    output_path = str(settings.output_path / f"{task_id}.json")

    metadata = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "progress": "0",
        "conversion_type": ConversionType.CSV_TO_JSON.value,
        "original_filename": file.filename,
        "original_filepath": file_path,
        "output_filepath": output_path,
        "created_at": datetime.utcnow().isoformat(),
        "file_size": str(file_size),
    }
    store_task_metadata(task_id, metadata)

    convert_csv_to_json.delay(task_id, file_path, output_path)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="CSV to JSON conversion task queued",
    )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_task_status(task_id: str):
    metadata = get_task_metadata(task_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Task not found")

    status = metadata.get("status", TaskStatus.PENDING.value)
    progress = int(metadata.get("progress", "0"))

    result_file = None
    if status == TaskStatus.COMPLETED.value:
        result_file = f"/api/v1/download/{task_id}"

    conversion_type = metadata.get("conversion_type")
    try:
        conversion_type = ConversionType(conversion_type) if conversion_type else None
    except ValueError:
        conversion_type = None

    return TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus(status),
        progress=progress,
        conversion_type=conversion_type,
        original_filename=metadata.get("original_filename"),
        result_file=result_file,
        error=metadata.get("error") if metadata.get("error") != "None" else None,
        created_at=metadata.get("created_at"),
        completed_at=metadata.get("completed_at") if metadata.get("completed_at") != "None" else None,
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    status: TaskStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    task_ids = get_all_task_ids()
    tasks = []

    for tid in task_ids:
        metadata = get_task_metadata(tid)
        if not metadata:
            continue

        task_status = metadata.get("status", TaskStatus.PENDING.value)
        if status and task_status != status.value:
            continue

        conversion_type = metadata.get("conversion_type")
        try:
            conversion_type = ConversionType(conversion_type) if conversion_type else None
        except ValueError:
            conversion_type = None

        tasks.append(
            TaskListItem(
                task_id=tid,
                status=TaskStatus(task_status),
                conversion_type=conversion_type,
                original_filename=metadata.get("original_filename"),
                progress=int(metadata.get("progress", "0")),
                created_at=metadata.get("created_at"),
            )
        )

    tasks.sort(key=lambda t: t.created_at or "", reverse=True)
    total = len(tasks)
    tasks = tasks[offset: offset + limit]

    return TaskListResponse(tasks=tasks, total=total)


@router.get("/download/{task_id}")
async def download_file(task_id: str):
    metadata = get_task_metadata(task_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Task not found")

    if metadata.get("status") != TaskStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Conversion not yet completed")

    output_path = metadata.get("output_filepath")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    original_filename = metadata.get("original_filename", "output")
    stem = Path(original_filename).stem
    ext = Path(output_path).suffix
    download_name = f"{stem}_converted{ext}"

    media_type_map = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".gif": "image/gif",
    }

    media_type = media_type_map.get(ext.lower(), "application/octet-stream")

    return FileResponse(
        path=output_path,
        filename=download_name,
        media_type=media_type,
    )


@router.delete("/tasks/{task_id}", response_model=dict)
async def delete_task(task_id: str):
    metadata = get_task_metadata(task_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Task not found")

    input_path = metadata.get("original_filepath")
    if input_path:
        Path(input_path).unlink(missing_ok=True)

    output_path = metadata.get("output_filepath")
    if output_path:
        Path(output_path).unlink(missing_ok=True)

    import redis
    client = redis.from_url(settings.redis_url, decode_responses=True)
    client.delete(f"task:{task_id}")
    client.srem("active_tasks", task_id)

    return {"detail": "Task and associated files deleted", "task_id": task_id}
