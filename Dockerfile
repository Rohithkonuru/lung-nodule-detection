# Root Dockerfile used by Render (service is configured for ./Dockerfile).
FROM python:3.11-slim

WORKDIR /app

# Install minimal system libs used by image processing dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from backend project folder.
COPY project/backend/requirements.txt project/backend/requirements-ml.txt /app/project/backend/
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/project/backend/requirements.txt \
    && pip install --no-cache-dir -r /app/project/backend/requirements-ml.txt

# Copy application source and model weights.
COPY project /app/project
COPY project/models /app/project/models

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/project/backend \
    UPLOAD_DIR=/app/project/backend/uploads/scans

WORKDIR /app/project/backend

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers"]
