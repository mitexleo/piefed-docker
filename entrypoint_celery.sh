#!/usr/bin/env sh
set -e

export FLASK_APP=pyfedi.py

echo "========================================="
echo "  PieFed - Starting Celery Worker"
echo "========================================="

# Wait for Redis to be available
if [ -n "$CELERY_BROKER_URL" ]; then
    echo "Waiting for Redis at $CELERY_BROKER_URL..."
    # Extract host from redis URL
    REDIS_HOST=$(echo "$CELERY_BROKER_URL" | sed -n 's/.*\/\/\([^:]*\).*/\1/p')
    REDIS_PORT=$(echo "$CELERY_BROKER_URL" | sed -n 's/.*:\([0-9]*\).*/\1/p')
    REDIS_PORT=${REDIS_PORT:-6379}

    if [ -n "$REDIS_HOST" ]; then
        for i in $(seq 1 30); do
            if nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
                echo "   Redis is ready!"
                break
            fi
            echo "   Waiting for Redis... ($i/30)"
            sleep 2
        done
    fi
fi

echo "Starting Celery worker..."
exec celery \
    -A celery_worker_docker.celery \
    worker \
    --concurrency=${CELERY_CONCURRENCY:-4} \
    --queues=${CELERY_QUEUES:-celery,background,send} \
    --loglevel=${LOG_LEVEL:-info}
