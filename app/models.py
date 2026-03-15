from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConversionType(str, Enum):
    PDF_TO_DOCX = "pdf_to_docx"
    IMAGE_CONVERT = "image_convert"
    CSV_TO_JSON = "csv_to_json"


class ImageFormat(str, Enum):
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    BMP = "bmp"
    TIFF = "tiff"
    GIF = "gif"


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    progress: int = Field(ge=0, le=100)
    conversion_type: Optional[ConversionType] = None
    original_filename: Optional[str] = None
    result_file: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskListItem(BaseModel):
    task_id: str
    status: TaskStatus
    conversion_type: Optional[ConversionType] = None
    original_filename: Optional[str] = None
    progress: int = 0
    created_at: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskListItem]
    total: int


class HealthResponse(BaseModel):
    status: str
    redis: str
    timestamp: str
    version: str


class ErrorResponse(BaseModel):
    detail: str
    status_code: int


class ConversionMetadata(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    conversion_type: ConversionType
    original_filename: str
    original_filepath: str
    output_filepath: Optional[str] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    file_size: int = 0
    target_format: Optional[str] = None
    quality: int = 85
