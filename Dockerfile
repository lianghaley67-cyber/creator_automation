FROM node:24-bookworm-slim AS frontend

WORKDIR /app/studio_frontend
COPY studio_frontend/package*.json ./
RUN npm ci
COPY studio_frontend/ ./
RUN npm run build


FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CREATOR_STUDIO_DATA_DIR=/app/studio_runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        espeak \
        libespeak1 \
        libglib2.0-0 \
        libgomp1 \
        fonts-noto-cjk \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY studio_backend/requirements.txt /app/studio_backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir -r /app/studio_backend/requirements.txt

COPY . /app
COPY --from=frontend /app/studio_frontend/dist /app/studio_frontend/dist

RUN mkdir -p /app/studio_runtime

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "studio_backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
