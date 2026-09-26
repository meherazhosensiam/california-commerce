# Deployment

Requirements: Ubuntu Server, Docker Engine, Docker Compose plugin.

```bash
cd california-commerce
mkdir -p data
sudo docker compose up --build -d
sudo docker compose ps
curl http://127.0.0.1:8080/api/health
```

Reset all application/database state:

```bash
docker compose down -v
docker compose up --build -d
```

The stack has PostgreSQL, Redis, FastAPI, a worker heartbeat, React/Nginx frontend, and an Nginx reverse proxy. PostgreSQL and Redis are not published to the host.
