import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "File Converter API"
    app_version: str = "1.0.0"
    debug: bool = False

    redis_url: str = "redis://localhost:6379/0"
    max_upload_size_mb: int = 50
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"
    cleanup_interval_hours: int = 1
    file_retention_hours: int = 24
    allowed_origins: str = "*"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def output_path(self) -> Path:
        path = Path(self.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
