FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY requirements-ml.txt /app/requirements-ml.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
	&& pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /app/requirements-ml.txt

COPY . /app

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
