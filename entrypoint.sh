#!/usr/bin/env sh
set -e

echo "========================================="
echo "  PieFed - Starting Web Service"
echo "========================================="

# Check required env vars
if [ -z "$SERVER_NAME" ]; then
    echo "❌ SERVER_NAME environment variable is required!"
    echo "   Set it to your domain (e.g., piefed.example.com) or 127.0.0.1:8030 for local testing."
    exit 1
fi

if [ -z "$SECRET_KEY" ]; then
    echo "❌ SECRET_KEY environment variable is required!"
    echo "   Generate one with: openssl rand -base64 32"
    exit 1
fi

# Fix permissions on volume mounts before starting the app.
# Volumes (named or bind) are owned by root initially.
# This chown ensures they're writable regardless of deployment config.
chown -R 1000:1000 /app/logs /app/app/static/media /app/app/static/tmp

export FLASK_APP=pyfedi.py

echo "1/4 Running database migrations..."
flask db upgrade

echo "2/4 Initializing database (if needed)..."
python /app/scripts/auto_init_db.py

echo "3/4 Populating community search index..."
flask populate_community_search

echo "4/4 Startup sequence complete"

echo ""
echo "========================================="
echo "  PieFed is ready! Starting Gunicorn..."
echo "========================================="

exec gunicorn \
    --config gunicorn.conf.py \
    --preload \
    --bind 0.0.0.0:5000 \
    --worker-tmp-dir /dev/shm \
    --workers ${GUNICORN_WORKERS:-2} \
    --threads ${GUNICORN_THREADS:-2} \
    --worker-class gthread \
    --max-requests 2000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level ${LOG_LEVEL:-info} \
    pyfedi:app
