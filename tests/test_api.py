import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from app.converter import CSVConverter, ImageConverter
from app.models import TaskStatus, ConversionType, ImageFormat


class TestHealthEndpoint:
    def test_health_check_returns_response(self, client):
        with patch("app.routes.redis") as mock_redis_module:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis_module.from_url.return_value = mock_client
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "redis" in data
            assert "timestamp" in data
            assert "version" in data


class TestRootEndpoint:
    def test_root_returns_api_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


class TestPDFConversion:
    def test_pdf_endpoint_rejects_non_pdf(self, client):
        file_content = b"not a pdf"
        response = client.post(
            "/api/v1/convert/pdf-to-docx",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_pdf_endpoint_accepts_pdf(self, client, mock_redis, mock_celery_tasks):
        file_content = b"%PDF-1.4 fake pdf content for testing"
        response = client.post(
            "/api/v1/convert/pdf-to-docx",
            files={"file": ("document.pdf", io.BytesIO(file_content), "application/pdf")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert mock_celery_tasks["pdf"].delay.called


class TestImageConversion:
    def test_image_endpoint_rejects_invalid_format(self, client):
        response = client.post(
            "/api/v1/convert/image",
            files={"file": ("test.xyz", io.BytesIO(b"data"), "application/octet-stream")},
            data={"target_format": "jpeg", "quality": "85"},
        )
        assert response.status_code == 400

    def test_image_endpoint_rejects_same_format(self, client):
        img_buffer = io.BytesIO()
        img = Image.new("RGB", (10, 10), color=(0, 0, 255))
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        response = client.post(
            "/api/v1/convert/image",
            files={"file": ("photo.png", img_buffer, "image/png")},
            data={"target_format": "png", "quality": "85"},
        )
        assert response.status_code == 400
        assert "same" in response.json()["detail"].lower()

    def test_image_endpoint_accepts_valid_request(self, client, mock_redis, mock_celery_tasks):
        img_buffer = io.BytesIO()
        img = Image.new("RGB", (10, 10), color=(0, 255, 0))
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        response = client.post(
            "/api/v1/convert/image",
            files={"file": ("photo.png", img_buffer, "image/png")},
            data={"target_format": "jpeg", "quality": "90"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert mock_celery_tasks["image"].delay.called


class TestCSVConversion:
    def test_csv_endpoint_rejects_non_csv(self, client):
        response = client.post(
            "/api/v1/convert/csv-to-json",
            files={"file": ("data.txt", io.BytesIO(b"some text"), "text/plain")},
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_csv_endpoint_accepts_csv(self, client, mock_redis, mock_celery_tasks):
        csv_content = b"name,age\nAlice,30\nBob,25\n"
        response = client.post(
            "/api/v1/convert/csv-to-json",
            files={"file": ("data.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert mock_celery_tasks["csv"].delay.called


class TestTaskEndpoints:
    def test_get_task_not_found(self, client, mock_redis):
        mock_redis["get"].return_value = None
        response = client.get("/api/v1/tasks/nonexistent-id")
        assert response.status_code == 404

    def test_get_task_found(self, client, mock_redis):
        mock_redis["get"].return_value = {
            "task_id": "test-123",
            "status": "completed",
            "progress": "100",
            "conversion_type": "pdf_to_docx",
            "original_filename": "test.pdf",
            "created_at": "2025-01-01T00:00:00",
            "completed_at": "2025-01-01T00:01:00",
            "error": "None",
            "output_filepath": "/tmp/out.docx",
        }
        response = client.get("/api/v1/tasks/test-123")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-123"
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["result_file"] == "/api/v1/download/test-123"

    def test_list_tasks_empty(self, client, mock_redis):
        mock_redis["list"].return_value = []
        response = client.get("/api/v1/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0


class TestCSVConverterUnit:
    def test_csv_to_json_conversion(self, sample_csv, temp_dirs):
        _, output_dir = temp_dirs
        output_path = str(Path(output_dir) / "output.json")
        CSVConverter.to_json(sample_csv, output_path)

        with open(output_path, "r") as f:
            result = json.load(f)

        assert "metadata" in result
        assert "data" in result
        assert result["metadata"]["total_records"] == 2
        assert len(result["data"]) == 2
        assert result["data"][0]["name"] == "Alice"
        assert result["data"][0]["age"] == 30
        assert result["data"][0]["active"] is True
        assert result["data"][1]["name"] == "Bob"
        assert result["data"][1]["age"] == 25
        assert result["data"][1]["active"] is False


class TestImageConverterUnit:
    def test_image_format_detection(self):
        assert ImageConverter.get_format_from_extension("photo.png") == ImageFormat.PNG
        assert ImageConverter.get_format_from_extension("photo.jpg") == ImageFormat.JPEG
        assert ImageConverter.get_format_from_extension("photo.jpeg") == ImageFormat.JPEG
        assert ImageConverter.get_format_from_extension("photo.webp") == ImageFormat.WEBP
        assert ImageConverter.get_format_from_extension("photo.bmp") == ImageFormat.BMP
        assert ImageConverter.get_format_from_extension("photo.gif") == ImageFormat.GIF
        assert ImageConverter.get_format_from_extension("photo.xyz") is None

    def test_image_conversion_png_to_jpeg(self, sample_image, temp_dirs):
        _, output_dir = temp_dirs
        output_path = str(Path(output_dir) / "output.jpg")
        result = ImageConverter.convert(sample_image, output_path, ImageFormat.JPEG, quality=85)
        assert Path(result).exists()
        img = Image.open(result)
        assert img.format == "JPEG"
        img.close()

    def test_image_validation(self, sample_image):
        info = ImageConverter.validate_image(sample_image)
        assert info["valid"] is True
        assert info["width"] == 100
        assert info["height"] == 100

    def test_image_validation_invalid(self):
        info = ImageConverter.validate_image("/nonexistent/path.png")
        assert info["valid"] is False


class TestEmptyFileUpload:
    def test_empty_file_rejected(self, client):
        response = client.post(
            "/api/v1/convert/csv-to-json",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
