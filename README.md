# PieFed Docker 🐳

> Dockerized deployment of [PieFed](https://codeberg.org/rimu/pyfedi) v1.6.23 — a Lemmy/Mbin alternative written in Python with Flask.

## Quick Start

```bash
# 1. Clone this repository
git clone https://github.com/mitexleo/piefed-docker.git
cd piefed-docker

# 2. Edit docker-compose.yml - change these values:
#    - SERVER_NAME: your domain (e.g., "piefed.example.com")
#    - SECRET_KEY: generate with: openssl rand -base64 32
#    - (Optional) ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD

# 3. Start everything
docker compose up -d

# 4. Visit http://localhost:8030 and log in with your admin credentials
```

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│   Web App   │    │   Celery    │    │  Notifs Svr  │
│  :5000      │    │  (workers)  │    │  :8000       │
│  Gunicorn   │    │  tasks      │    │  FastAPI/SSE │
└──────┬──────┘    └──────┬──────┘    └──────┬───────┘
       │                  │                  │
       └──────────┬───────┴──────────┬───────┘
                  │                  │
           ┌──────▼──────┐   ┌──────▼──────┐
           │  PostgreSQL │   │    Redis    │
           │  :5432      │   │  :6379      │
           └─────────────┘   └─────────────┘
```

| Service | Port (Host) | Description |
|---------|-------------|-------------|
| **web** | `8030` | Flask app served via Gunicorn (WSGI) |
| **celery** | — | Background task processing (federation, email, cleanup) |
| **notifs** | `8040` | Real-time notifications via SSE (FastAPI/Uvicorn) |
| **db** | — | PostgreSQL 17 |
| **redis** | — | Redis 7 cache & message broker |

## Configuration

### Required Settings

Edit `docker-compose.yml` in the `web` service's `environment` section:

| Variable | Description | Example |
|----------|-------------|---------|
| `SERVER_NAME` | Your domain (no protocol) | `"piefed.example.com"` |
| `SECRET_KEY` | Random string, 32+ chars | `openssl rand -base64 32` |

### Admin Account (First Run)

Set these before the first `docker compose up`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_USERNAME` | `admin` | Initial admin username |
| `ADMIN_EMAIL` | (empty) | Admin email (optional) |
| `ADMIN_PASSWORD` | (auto-generated) | Admin password (printed to logs on first run) |

If `ADMIN_PASSWORD` is not set, a random password will be generated and printed to the web service logs on the first startup. Retrieve it with:

```bash
docker compose logs web | grep "Admin password"
```

### Optional Features

Uncomment the relevant sections in `docker-compose.yml` to enable:

- **Email** — SMTP configuration for notifications
- **Real-time notifications** — Uncomment `NOTIF_SERVER` and use the `notifs` service
- **S3 storage** — Remote media storage (AWS S3, MinIO, etc.)
- **Sentry** — Error monitoring
- **Stripe** — Donations/subscriptions
- **LDAP** — Directory authentication
- **OAuth** — Google, Mastodon, Discord login
- **Cloudflare** — API token for cache purging
- **Translation** — LibreTranslate integration

## Production Deployment

### Reverse Proxy

For production, place PieFed behind a reverse proxy (Nginx, Caddy, Traefik) that handles SSL termination.

Example Nginx config:

```nginx
server {
    listen 443 ssl;
    server_name piefed.example.com;

    location / {
        proxy_pass http://127.0.0.1:8030;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for notifications
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Important:** After setting up the reverse proxy, update these environment variables:
- `SERVER_NAME` — Set to your domain (e.g., `"piefed.example.com"`)
- `HTTP_PROTOCOL` — Set to `"https"`
- `SESSION_COOKIE_SECURE` — Set to `1`

### Cron Jobs

Add these to your host's crontab (`crontab -e`):

```cron
5 2 * * * docker exec piefed_app bash -c "cd /app && python -m app.cli daily_maintenance"
5 4 * * 1 docker exec piefed_app bash -c "cd /app && python -m app.cli remove_orphan_files"
1 */6 * * * docker exec piefed_app bash -c "cd /app && python -m app.cli send_missed_notifs"
*/1 * * * * docker exec piefed_app bash -c "cd /app && python -m app.cli send_queue"
```

## Maintenance Commands

```bash
# View logs
docker compose logs -f web
docker compose logs -f celery

# Stop all services
docker compose down

# Rebuild and restart (after config changes or updates)
docker compose up -d --build

# Access the shell inside the web container
docker exec -it piefed_app sh

# Run Flask commands
docker exec -it piefed_app sh -c "cd /app && FLASK_APP=pyfedi.py flask init-db"

# View database (Adminer)
# Uncomment the adminer service in docker-compose.yml and visit http://localhost:8888
```

## Updating

```bash
# Pull latest source (includes updated piefed source)
git pull

# Rebuild and restart
docker compose up -d --build
```

> **Note:** Version updates are handled automatically by the GitHub Actions workflow.
> The `mitexleo/piefed-docker:v1.6.23` image is rebuilt and pushed whenever a new PieFed release is tagged.

## Data Persistence

Data is stored in Docker named volumes:

| Volume | Contents | 
|--------|----------|
| `pgdata` | PostgreSQL database |
| `redis_data` | Redis cache data |
| `media_data` | Uploaded media files |
| `logs_data` | Application logs |
| `tmp_data` | Temporary files |

To backup:

```bash
docker run --rm -v piefed-docker_pgdata:/data -v $(pwd):/backup alpine tar czf /backup/pgdata-backup.tar.gz -C /data .
```

## Troubleshooting

**"Internal Server Error" on first load**
→ Database may not be initialized yet. Check `docker compose logs web` and wait for the init process to complete.

**Permission errors with media uploads**
→ Ensure the `user: "1000:1000"` in the db service matches the UID on your host system. Adjust if needed.

**"SECRET_KEY is not set"**
→ Generate a key: `openssl rand -base64 32` and set it in `docker-compose.yml`

## License

This project is licensed under AGPL-3.0, matching the upstream PieFed license.
