```
  _____ _ _         ____                          _              _    ____ ___
 |  ___(_) | ___   / ___|___  _ ____   _____ _ __| |_ ___ _ __  / \  |  _ \_ _|
 | |_  | | |/ _ \ | |   / _ \| '_ \ \ / / _ \ '__| __/ _ \ '__|/ _ \ | |_) | |
 |  _| | | |  __/ | |__| (_) | | | \ V /  __/ |  | ||  __/ | / ___ \|  __/| |
 |_|   |_|_|\___|  \____\___/|_| |_|\_/ \___|_|   \__\___|_|/_/   \_\_|  |___|

```

[![Build Status](https://img.shields.io/github/actions/workflow/status/N3XT3R1337/file-converter-api/ci.yml?branch=main&style=for-the-badge)](https://github.com/N3XT3R1337/file-converter-api/actions)
[![License](https://img.shields.io/github/license/N3XT3R1337/file-converter-api?style=for-the-badge)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7+-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5+-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev)

---

A high-performance file conversion REST API built with **FastAPI**, **Celery**, and **Redis**. Upload files, convert between formats asynchronously, track progress in real-time, and download results — all through a clean RESTful interface.

---

## Features

- **PDF to DOCX** — Extract text and structure from PDFs into editable Word documents
- **Image Format Conversion** — Convert between PNG, JPEG, WEBP, BMP, TIFF, and GIF
- **CSV to JSON** — Transform CSV data into structured JSON output
- **Async Task Queue** — Powered by Celery + Redis for reliable background processing
- **Real-Time Progress** — Track conversion status and progress percentage via polling
- **Auto Cleanup** — Scheduled cleanup of expired files and completed tasks
- **Upload Size Limits** — Configurable max upload size with validation
- **Health Checks** — Built-in health and readiness endpoints
- **CORS Support** — Configurable cross-origin resource sharing
- **Docker Ready** — Full Docker Compose setup for instant deployment

---

## Tech Stack

| Component      | Technology           |
|---------------|----------------------|
| Web Framework | FastAPI              |
| Task Queue    | Celery 5             |
| Message Broker| Redis 7              |
| PDF Parsing   | PyMuPDF (fitz)       |
| DOCX Creation | python-docx          |
| Image Processing | Pillow            |
| Testing       | pytest + httpx       |
| Containerization | Docker + Compose  |

---

## Installation

### Prerequisites

- Python 3.11+
- Redis server running on `localhost:6379`

### Local Setup

```bash
git clone https://github.com/N3XT3R1337/file-converter-api.git
cd file-converter-api

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Docker Setup

```bash
docker-compose up --build
```

---

## Usage

### Start the API Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Start the Celery Worker

```bash
celery -A app.tasks worker --loglevel=info
```

### Start the Cleanup Scheduler

```bash
celery -A app.tasks beat --loglevel=info
```

---

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "redis": "connected",
  "timestamp": "2025-10-10T16:45:00Z"
}
```

### Convert PDF to DOCX

```bash
curl -X POST http://localhost:8000/api/v1/convert/pdf-to-docx \
  -F "file=@document.pdf" \
  -o result.json
```

```json
{
  "task_id": "abc123-def456",
  "status": "pending",
  "message": "Conversion task queued"
}
```

### Convert Image Format

```bash
curl -X POST http://localhost:8000/api/v1/convert/image \
  -F "file=@photo.png" \
  -F "target_format=webp" \
  -F "quality=85"
```

### Convert CSV to JSON

```bash
curl -X POST http://localhost:8000/api/v1/convert/csv-to-json \
  -F "file=@data.csv"
```

### Check Task Status

```bash
curl http://localhost:8000/api/v1/tasks/abc123-def456
```

```json
{
  "task_id": "abc123-def456",
  "status": "completed",
  "progress": 100,
  "result_file": "/api/v1/download/abc123-def456"
}
```

### Download Converted File

```bash
curl -O http://localhost:8000/api/v1/download/abc123-def456
```

### List Active Tasks

```bash
curl http://localhost:8000/api/v1/tasks
```

---

## Configuration

Environment variables for customization:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum upload file size in MB |
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded files |
| `OUTPUT_DIR` | `./outputs` | Directory for converted files |
| `CLEANUP_INTERVAL_HOURS` | `1` | Interval for cleanup scheduler |
| `FILE_RETENTION_HOURS` | `24` | How long to keep files before cleanup |
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
file-converter-api/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── routes.py
│   ├── tasks.py
│   ├── converter.py
│   └── scheduler.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_api.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 panaceya (N3XT3R1337)
