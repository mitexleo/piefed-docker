# syntax=docker/dockerfile:1.4
FROM --platform=$BUILDPLATFORM python:3.13-alpine AS builder

LABEL org.opencontainers.image.title="PieFed"
LABEL org.opencontainers.image.description="A Lemmy/Mbin alternative written in Python with Flask"
LABEL org.opencontainers.image.url="https://codeberg.org/rimu/pyfedi"
LABEL org.opencontainers.image.source="https://codeberg.org/rimu/pyfedi"
LABEL org.opencontainers.image.version="1.6.23"
LABEL org.opencontainers.image.licenses="AGPL-3.0"

RUN adduser -D python

# Install system dependencies for building and runtime
RUN apk add --no-cache \
    pkgconfig \
    gcc \
    python3-dev \
    musl-dev \
    tesseract-ocr \
    tesseract-ocr-data-eng \
    postgresql-client \
    bash \
    py3-pip

# Install Python dependencies
COPY piefed/requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --no-cache-dir -r /tmp/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --no-cache-dir gunicorn

# Copy application code
COPY piefed /app

WORKDIR /app

# Compile translations (best-effort, may fail if no .po files)
RUN pybabel compile -d app/translations || true

# Create required directories with proper permissions
RUN mkdir -p /app/app/static/media /app/logs /app/app/static/tmp && \
    chown -R python:python /app

# Copy custom entrypoints and init scripts
COPY entrypoint.sh /app/entrypoint.sh
COPY entrypoint_celery.sh /app/entrypoint_celery.sh
COPY entrypoint_notifs.sh /app/entrypoint_notifs.sh
COPY scripts/ /app/scripts/

RUN chmod +x /app/entrypoint.sh /app/entrypoint_celery.sh /app/entrypoint_notifs.sh

USER python

EXPOSE 5000 8000

ENTRYPOINT ["./entrypoint.sh"]
