#!/usr/bin/env sh
set -e

echo "========================================="
echo "  PieFed - Starting Notifications Server"
echo "========================================="

# Wait for Redis to be available
if [ -n "$CACHE_REDIS_URL" ]; then
    echo "Waiting for Redis at $CACHE_REDIS_URL..."
    REDIS_HOST=$(echo "$CACHE_REDIS_URL" | sed -n 's/.*\/\/\([^:]*\).*/\1/p')
    REDIS_PORT=$(echo "$CACHE_REDIS_URL" | sed -n 's/.*:\([0-9]*\).*/\1/p')
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

echo "Starting Uvicorn..."
exec uvicorn \
    fastapi_server:app \
    --host 0.0.0.0 \
    --port ${NOTIF_PORT:-8000} \
    --log-level ${LOG_LEVEL:-info}
