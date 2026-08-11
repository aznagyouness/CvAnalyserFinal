# Docker & Infrastructure Setup Guide for CvanalyserFinal

## Table of Contents
1. [Project Structure](#1-project-structure)
2. [Docker Compose Services](#2-docker-compose-services)
3. [Environment Variables](#3-environment-variables)
   - [Root .env / .env.dev (Application Variables)](#root-env--envdev-application-variables)
   - [Docker env Files (Container Variables)](#docker-env-files-container-variables)
4. [Configuration Files](#4-configuration-files)
   - [RabbitMQ Config](#rabbitmq-config)
   - [Prometheus Config](#prometheus-config)
   - [Nginx Config](#nginx-config)
   - [FastAPI Dockerfile](#fastapi-dockerfile)
5. [Port Troubleshooting: Diagnostic & Solution](#5-port-troubleshooting-diagnostic--solution)
   - [How We Diagnosed the Problem](#how-we-diagnosed-the-problem)
   - [Root Cause: Windows Reserved Port Ranges](#root-cause-windows-reserved-port-ranges)
   - [Final Solution](#final-solution)
6. [Common Commands](#6-common-commands)
7. [Understanding Docker: .env vs .conf Files](#7-understanding-docker-env-vs-conf-files)

---

## 1. Project Structure
```
CvanalyserFinal/
├── docker/
│   ├── env/
│   │   ├── .env.app              # FastAPI app (when run INSIDE Docker)
│   │   ├── .env.grafana          # Grafana admin credentials
│   │   ├── .env.mongodb          # MongoDB (optional, commented out)
│   │   ├── .env.mongodb-exporter # MongoDB exporter (optional)
│   │   ├── .env.postgres         # PostgreSQL user/pass/db
│   │   ├── .env.postgres-exporter# PostgreSQL exporter
│   │   ├── .env.rabbitmq         # RabbitMQ user, vhost, PORT!
│   │   └── .env.redis            # Redis password, PORT!, memory limits
│   ├── minirag/
│   │   └── Dockerfile            # Builds FastAPI image for production
│   ├── nginx/
│   │   └── default.conf          # Reverse proxy: 80 → fastapi:8080
│   ├── prometheus/
│   │   └── prometheus.yml        # Metrics targets: FastAPI, Qdrant, Exporters
│   ├── rabbitmq/
│   │   └── rabbitmq.conf         # RabbitMQ tuning (memory, disk, management)
│   └── .gitignore
├── docker-compose.yml            # All services definition ← START HERE
├── .env                          # Production app settings (localhost)
└── .env.dev                      # Dev app settings (localhost)
```

---

## 2. Docker Compose Services
All containers are defined in **[docker-compose.yml](../docker-compose.yml)**. They share a user-defined bridge network called `backend` (line 281), and all have `restart: always`.

### Active Services (Running):
| Service | Container Name | Image | Host Port → Container Port | Purpose |
|---------|---------------|-------|--------------------------|---------|
| **qdrant** | `qdrant` | `qdrant/qdrant:v1.17.0` | `6333:6333`<br>`6334:6334` | Vector Database (REST API + gRPC) |
| **prometheus** | `prometheus` | `prom/prometheus:v3.3.0` | `9090:9090` | Metrics scraper & storage |
| **grafana** | `grafana` | `grafana/grafana:11.6.0-ubuntu` | `3000:3000` | Dashboard / visualization |
| **node-exporter** | `node-exporter` | `prom/node-exporter:v1.9.1` | `9100:9100` | OS-level metrics (CPU, RAM, disk) |
| **rabbitmq** | `rabbitmq` | `rabbitmq:4.1.2-management-alpine` | `7021:7021`<br>`15672:15672` | AMQP message broker + management UI |
| **redis** | `redis` | `redis:8.0.3-alpine` | `7020:7020` | Results backend / cache / idempotency |
| **pgvector** | `pgvector` | `pgvector/pgvector:0.8.0-pg17` | `5432:5432` | PostgreSQL + pgvector extension |
| **postgres-exporter** | `postgres-exporter` | `prometheuscommunity/postgres-exporter:v0.17.1` | `9187:9187` | Postgres metrics for Prometheus |

### Commented-Out Services (Not Running):
- **fastapi** (lines 4-24, 133-150): Two alternate definitions for running FastAPI itself inside Docker. Currently disabled because you run FastAPI locally (`python -m uvicorn src.main:app --reload`).
- **nginx** (lines 28-39): Reverse proxy in front of FastAPI when running in Docker.
- **mongodb** + **mongodb-exporter**: Extra optional database.

### Volumes
All data is persisted via Docker named volumes (line 284-291):
```
fastapi_data, qdrant_data, prometheus_data, grafana_data,
rabbitmq_data, redis_data, pgvector
```

---

## 2.1 Architecture Diagram (Mermaid)

This diagram shows how all components connect. Mermaid renders natively in VS Code, GitHub, and most Markdown viewers. If this fails to render in your preview, try opening the file in GitHub or use the [Mermaid Live Editor](https://mermaid.live).

```mermaid
graph TB
    classDef host fill:#f9f,stroke:#333,stroke-width:2px,color:#000
    classDef broker fill:#ff9,stroke:#333,stroke-width:2px,color:#000
    classDef db fill:#9f9,stroke:#333,stroke-width:2px,color:#000
    classDef mon fill:#f99,stroke:#333,stroke-width:2px,color:#000
    classDef user fill:#fff,stroke:#333,stroke-width:2px,color:#000,stroke-dasharray:5 5
    classDef opt fill:#eee,stroke:#aaa,stroke-width:2px,stroke-dasharray:5 5,color:#000

    %% ==== NODES ====
    User((User or Client))
    Nginx[Nginx Reverse Proxy port 80 OPTIONAL]
    FastAPI[FastAPI on HOST localhost 8000]

    subgraph DockerBackend [Docker Containers on network backend]
        RabbitMQ[RabbitMQ port 7021 AMQP port 15672 Mgmt]
        Redis[Redis port 7020 DB 0 1 2]
        Postgres[PostgreSQL pgvector port 5432]
        Qdrant[Qdrant VectorDB port 6333 REST port 6334 gRPC]
        Prometheus[Prometheus scraper port 9090]
        Grafana[Grafana Dashboards port 3000]
        NodeExporter[Node Exporter port 9100]
        PostgresExporter[Postgres Exporter port 9187]
    end

    %% ==== EDGES (no numbers with dots, only letters and dashes) ====
    User -- HTTP --> Nginx
    Nginx -- if FastAPI runs in Docker --> FastAPI
    User -- HTTP direct dev mode --> FastAPI

    FastAPI -- Step1 Submit background task --> RabbitMQ
    FastAPI -- Step3 Quota Results Idempotency --> Redis
    FastAPI -- Step4 Relational pgvector data --> Postgres
    FastAPI -- Step5 Vector Search QDRANT --> Qdrant

    NodeExporter -- scraped --> Prometheus
    PostgresExporter -- scraped --> Prometheus
    Postgres -- connection --> PostgresExporter
    Qdrant -- scraped --> Prometheus
    Prometheus -- datasource --> Grafana
    Grafana -- queries --> Prometheus

    %% ==== EXPLICIT STYLE ASSIGNMENTS (SAFER THAN INLINE) ====
    class FastAPI host
    class RabbitMQ broker
    class Redis,Postgres,Qdrant db
    class Prometheus,Grafana,NodeExporter,PostgresExporter mon
    class User user
    class Nginx opt
```

**How to read the arrows**:
1. **User -> FastAPI (or Nginx)**: HTTP requests from client. Development = direct to port 8000. Production Docker = through Nginx on port 80.
2. **FastAPI <-> RabbitMQ**: Taskiq broker (FastAPI submits tasks; workers consume tasks).
3. **FastAPI -> Redis**: Reads / writes task results, quota manager state, idempotency deduplication keys.
4. **FastAPI -> PostgreSQL**: All relational data (users, task history) plus pgvector embeddings.
5. **FastAPI -> Qdrant**: Vector similarity search, only if `VECTOR_DB_BACKEND="QDRANT"` in .env.
6. **Monitoring**: Prometheus scrapes every /metrics endpoint (Node Exporter, Postgres Exporter, Qdrant). Grafana displays Prometheus data in dashboards.

**Legend (colors in diagram)**:
| Color | Type | What |
|---|---|---|
| Pink | HOST (not Docker) | FastAPI Uvicorn (you run it locally: `python -m uvicorn src.main:app`) |
| Yellow | Broker / Queue | RabbitMQ (Taskiq message broker) |
| Green | Database / Storage | Redis, PostgreSQL + pgvector, Qdrant |
| Red | Monitoring | Prometheus, Grafana, Node Exporter, Postgres Exporter |
| Dashed Gray | Optional | Nginx (only used if you later deploy FastAPI *inside* Docker) |
| Dashed White | External | User / Client (browser, HTTP client) |

**Port Reference Quick Table** (all reachable via `localhost:<port>` from your host):
| Service | Port | Protocol | Purpose |
|---|---|---|---|
| FastAPI | `8000` | HTTP | Your application API |
| RabbitMQ | `7021` | AMQP | Task queue (Taskiq) |
| RabbitMQ Mgmt | `15672` | HTTP | Web UI to inspect queues |
| Redis | `7020` | RESP | Result backend + quota + idempotency |
| PostgreSQL | `5432` | PostgreSQL wire | Relational data + pgvector |
| Qdrant | `6333` | HTTP | Vector search REST |
| Qdrant | `6334` | gRPC | Vector search gRPC (Python client) |
| Prometheus | `9090` | HTTP | Metrics scraper UI + API |
| Grafana | `3000` | HTTP | Dashboards |
| Node Exporter | `9100` | HTTP | OS metrics endpoint |
| Postgres Exporter | `9187` | HTTP | PostgreSQL metrics endpoint |

---

## 3. Environment Variables

### Root .env / .env.dev (Application Variables)
These are used by **your Python code running on the host**. All connection URLs use `localhost:<host-port>` because FastAPI runs locally and connects to Docker-exposed ports.

#### 🔴 Redis (Port 7020) — DB 0, 1, 2
```env
# Line 39: Celery result backend (DB 0)
CELERY_RESULT_BACKEND_URL="redis://:minirag_redis_2222@localhost:7020/0"

# Line 50: Quota Manager (DB 0)
REDIS_URL_QUOTA="redis://:minirag_redis_2222@localhost:7020/0"

# Line 53: Taskiq Result Backend (DB 1)
REDIS_URL_TASKIQ_RESULTS="redis://:minirag_redis_2222@localhost:7020/1"

# Line 56: Taskiq Rate Limiter (DB 2)
REDIS_URL_TASKIQ_LIMITER="redis://:minirag_redis_2222@localhost:7020/2"
```
**Format**: `redis://:PASSWORD@HOST:PORT/DB_INDEX`
- Password is `minirag_redis_2222` (matches [docker/env/.env.redis](docker/env/.env.redis#L2))
- Uses separate logical DBs for separate concerns (quota vs results vs limiter) — same Redis instance, isolated keyspaces.

#### 🐇 RabbitMQ / Taskiq (Port 7021)
```env
# Line 38: Legacy Celery broker URL
CELERY_BROKER_URL="amqp://minirag_user:minirag_rabbitmq_0000@localhost:7021/minirag_vhost"

# Line 46: Active Taskiq broker URL
TASKIQ_BROKER_URL="amqp://minirag_user:minirag_rabbitmq_0000@localhost:7021/minirag_vhost"
```
**Format**: `amqp://USER:PASSWORD@HOST:PORT/VHOST`
- User: `minirag_user` (matches [docker/env/.env.rabbitmq](docker/env/.env.rabbitmq#L2))
- Password: `minirag_rabbitmq_0000` (matches [docker/env/.env.rabbitmq](docker/env/.env.rabbitmq#L3))
- VHost: `minirag_vhost` (matches [docker/env/.env.rabbitmq](docker/env/.env.rabbitmq#L4))

#### 🐘 PostgreSQL (Port 5432)
```env
# Line 62: Async SQLAlchemy + pgvector
POSTGRES_DATABASE_URL=postgresql+asyncpg://postgres1:postgres_password1@localhost:5432/essai_for_celery_db
```
**Format**: `postgresql+asyncpg://USER:PASS@HOST:PORT/DB`
- Credentials match [docker/env/.env.postgres](docker/env/.env.postgres#L2-L4).

#### 🟠 Qdrant (Port 6333)
```env
# Line 75: Qdrant REST API
VECTOR_DB_URL = "http://localhost:6333"
VECTOR_DB_COLLECTION_NAME = "docker_dev"
```

#### 🔵 Monitoring Ports
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (user: `admin`, pass from [docker/env/.env.grafana](docker/env/.env.grafana#L3))
- Node Exporter: `http://localhost:9100/metrics`
- Postgres Exporter: `http://localhost:9187/metrics`

---

### Docker env Files (Container Variables)
These live in `docker/env/` and are injected **inside the containers themselves** (NOT read by your host Python).

#### 📄 [docker/env/.env.redis](docker/env/.env.redis)
| Variable | Value | Purpose |
|----------|-------|---------|
| `REDIS_PASSWORD` | `minirag_redis_2222` | AUTH password required for clients |
| `REDIS_APPENDONLY` | `yes` | AOF persistence (survives restarts) |
| `REDIS_MAXMEMORY` | `512mb` | Max RAM Redis can use |
| `REDIS_MAXMEMORY_POLICY` | `allkeys-lru` | Evict least-recently-used keys when full |
| `REDIS_PROTECTED_MODE` | `yes` | Require password for external connections |
| `REDIS_PORT` | `6426` ⚠️ **NEEDS UPDATE** | Internal listen port — should be `7020` to match compose mapping! |

#### 📄 [docker/env/.env.rabbitmq](docker/env/.env.rabbitmq)
| Variable | Value | Purpose |
|----------|-------|---------|
| `RABBITMQ_DEFAULT_USER` | `minirag_user` | Auto-created admin user on first boot |
| `RABBITMQ_DEFAULT_PASS` | `minirag_rabbitmq_0000` | User password |
| `RABBITMQ_DEFAULT_VHOST` | `minirag_vhost` | Auto-created virtual host on first boot |
| `RABBITMQ_MANAGEMENT_ENABLED` | `true` | Enables :15672 web UI |
| `RABBITMQ_NODE_PORT` | `5821` ⚠️ **NEEDS UPDATE** | Internal AMQP port — should be `7021` to match compose `7021:7021`! |

#### 📄 [docker/env/.env.postgres](docker/env/.env.postgres)
| Variable | Value | Purpose |
|----------|-------|---------|
| `POSTGRES_USER` | `postgres1` | Auto-created superuser |
| `POSTGRES_PASSWORD` | `postgres_password1` | Superuser password |
| `POSTGRES_DB` | `essai_for_celery_db` | Auto-created DB |
| `POSTGRES_PORT` | `5432` | Container port (matches default) |

#### 📄 [docker/env/.env.grafana](docker/env/.env.grafana)
| Variable | Value | Purpose |
|----------|-------|---------|
| `GF_SECURITY_ADMIN_USER` | `admin` | Grafana web UI username |
| `GF_SECURITY_ADMIN_PASSWORD` | `admin_password` | Grafana web UI password |
| `GF_USERS_ALLOW_SIGN_UP` | `false` | Disable public signups |

---

## 4. Configuration Files

### RabbitMQ Config
**[docker/rabbitmq/rabbitmq.conf](docker/rabbitmq/rabbitmq.conf)**
```ini
vm_memory_high_watermark.relative = 0.6   # Max 60% of host RAM
disk_free_limit.absolute = 2GB             # Stop accepting writes if disk < 2GB
management.tcp.port = 15672                # Web UI port
log.console.level = info                   # Console log verbosity
```

### Prometheus Config
**[docker/prometheus/prometheus.yml](docker/prometheus/prometheus.yml)**
Scrapes every 15s. Targets are resolved via Docker DNS (container names on `backend` network):
- `fastapi:8080/TrhBVe_m5gg2002_E5VVqS` → FastAPI metrics endpoint (only used if FastAPI runs in Docker)
- `node-exporter:9100` → Host OS metrics
- `localhost:9090` → Prometheus itself
- `qdrant:6333/metrics` → Qdrant vector DB metrics
- `postgres-exporter:9187/metrics` → PostgreSQL metrics

### Nginx Config
**[docker/nginx/default.conf](docker/nginx/default.conf)**
Only used if FastAPI + Nginx run in Docker:
- Listens on port 80
- `client_max_body_size 2000000M` → Allows huge file uploads (2 TB)
- Proxies `/` → `http://fastapi:8080`
- Proxies `/TrhBVe_m5gg2002_E5VVqS` → FastAPI metrics path directly

### FastAPI Dockerfile
**[docker/minirag/Dockerfile](docker/minirag/Dockerfile)**
Production build:
- Base: `uv:0.6.14-python3.10-bookworm` (Astral UV package manager)
- Installs system libs for lxml, PDFs, images, libuv
- Copies `requirements.txt` → installs via `uv pip`
- Copies `src/` → `/app/`
- Runs: `uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4`

---

## 5. Port Troubleshooting: Diagnostic & Solution

### How We Diagnosed the Problem
We were getting these errors on FastAPI startup:
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6426. Connection refused.
aiormq.exceptions.AMQPConnectionError: Server connection reset: ConnectionResetError(104)
```

#### Diagnostic Steps Performed:
1. **Listened for ports**: `netstat -ano | findstr :6426` → nothing listening on host.
2. **Inspected Redis container**: `docker inspect redis` → looked at `NetworkSettings.Ports`:
   ```json
   "6426/tcp": []   ← EMPTY! Port NOT actually published!
   ```
   (Even though `HostConfig.PortBindings` was set.)
3. **Tried to recreate Redis via compose**: Got the smoking-gun error:
   ```
   Error response from daemon: ports are not available: exposing port TCP 0.0.0.0:6426 -> 127.0.0.1:0:
   /forwards/expose returned unexpected status: 500
   ```
4. **Checked Windows excluded port ranges** (PowerShell admin):
   ```powershell
   netsh interface ipv4 show excludedportrange protocol=tcp
   ```

### Root Cause: Windows Reserved Port Ranges
WSL/Hyper-V pre-reserves blocks of ports that Docker Desktop **cannot bind**, even if they're free:

| Start Port | End Port | Blocked By |
|-----------|---------|------------|
| 5738 | 5837 | Hyper-V |
| 6366 | 6465 | Hyper-V |

- **Old Redis port: `6426`** → inside 6366-6465 ❌ BLOCKED
- **Old RabbitMQ port: `5821`** → inside 5738-5837 ❌ BLOCKED

Docker can't publish them → internal `/forwards/expose` API returns HTTP 500 → containers seem "running" but host can't actually connect.

### Final Solution
Moved both services to **safe ports (7020 / 7021)** that are NOT in any excluded range. These are the required config changes to make it work:

#### ✅ Changes Needed (Apply All):
1. **[docker-compose.yml](../docker-compose.yml#L158-L178)**
   - RabbitMQ ports: `7021:7021`
   - Redis ports: `7020:7020`
2. **[docker/env/.env.redis](docker/env/.env.redis#L15)**
   - `REDIS_PORT=7020` (was 6426)
3. **[docker/env/.env.rabbitmq](docker/env/.env.rabbitmq#L16)**
   - `RABBITMQ_NODE_PORT=7021` (was 5821)
4. **Root [.env](../.env#L38-L56) + [.env.dev](../.env.dev#L38-L56)**
   - All `@localhost:5821` → `@localhost:7021` (RabbitMQ URL)
   - All `@localhost:6426` → `@localhost:7020` (Redis URL)

#### ✅ Apply Changes:
```bash
# 1. Shut down & remove the old port-stuck containers
docker compose -f docker-compose.yml down

# 2. Start fresh with correct mappings
docker compose -f docker-compose.yml up -d

# 3. Wait 25s for RabbitMQ to fully initialize
sleep 25

# 4. Verify all 4 ports work from WSL
nc -zv localhost 7020   # Redis → should say "succeeded"
nc -zv localhost 7021   # RabbitMQ → should say "succeeded"
nc -zv localhost 5432   # PostgreSQL
nc -zv localhost 6333   # Qdrant

# 5. Double-check container internal listeners
docker exec rabbitmq rabbitmq-diagnostics listeners   # Look for: Interface: [::], port: 7021, protocol: amqp
docker exec redis redis-cli -a minirag_redis_2222 -p 7020 ping   # → PONG

# 6. Now start FastAPI
python -m uvicorn src.main:app --reload --port 8000
```

Expected happy startup logs:
```
✅ settings loaded.
✅ Database Engine and Session Factory initialized.
✅ Global Quota Managers initialized.
[info] TaskiqIdempotencyMiddleware connected to Redis
[info] ✅ Taskiq broker started
[info] Application startup complete.
```

---

## 6. Common Commands
```bash
# Start all services (daemon)
docker compose -f docker-compose.yml up -d

# Recreate one service (e.g. after changing env/config)
docker compose -f docker-compose.yml up -d --force-recreate rabbitmq redis

# Stop all
docker compose -f docker-compose.yml stop

# Stop + remove containers (keeps volumes)
docker compose -f docker-compose.yml down

# Stop + REMOVE VOLUMES (WIPES ALL DATA!)
docker compose -f docker-compose.yml down -v

# View logs for one service
docker logs -f rabbitmq
docker logs -f --tail 50 redis

# Exec into a container
docker exec -it redis sh
docker exec -it rabbitmq rabbitmqctl list_vhosts
docker exec -it pgvector psql -U postgres1 -d essai_for_celery_db

# Show actual published ports (not requested)
docker port redis
docker port rabbitmq

# Health check statuses
docker inspect redis --format '{{.State.Health.Status}}'
docker inspect rabbitmq --format '{{.State.Health.Status}}'
```

---

## 7. Understanding Docker: .env vs .conf Files
Your intuition is exactly right! Docker uses **two different kinds of configuration files** that work together:

### `.env` Files = "Startup / Bootstrap Setup" (Container Creation Time)
These files set **environment variables** that Docker injects into the container **when it is first created** (during `docker compose up` or `docker run`).

**What they do**:
- Configure the container's **initial identity** (users, passwords, default DBs, vhosts, listening ports).
- Many official Docker images (RabbitMQ, Redis, Postgres, Grafana) have "first-run" scripts that read env vars and auto-configure the service *once* on initial boot.
- **Think of it like filling out a form when you first install an app**.

**Examples from your project**:
- [docker/env/.env.rabbitmq](docker/env/.env.rabbitmq):
  - `RABBITMQ_DEFAULT_USER=minirag_user` — RabbitMQ auto-creates this user **the first time the container starts**.
  - `RABBITMQ_DEFAULT_VHOST=minirag_vhost` — RabbitMQ auto-creates this vhost on first boot.
  - `RABBITMQ_NODE_PORT=7021` — Tells RabbitMQ what TCP port to listen on inside the container.
- [docker/env/.env.redis](docker/env/.env.redis):
  - `REDIS_PASSWORD=minirag_redis_2222` — Sets the Redis AUTH password via CLI flags in compose.
  - `REDIS_PORT=7020` — Tells Redis what port to bind to.

**Key trait**: If you edit a `.env` file, you must **recreate the container** for the change to take effect:
```bash
docker compose -f docker-compose.yml up -d --force-recreate rabbitmq
```

---

### `.conf` / `.yml` / mounted config files = "Ongoing Runtime Behavior" (Container Running Time)
These files are **regular text files mounted from your host into the container's filesystem** via `volumes:` in docker-compose.yml. The running service reads them *every time it starts up* or even reloads them on the fly.

**What they do**:
- Fine-tune the service **day-to-day** (memory limits, disk thresholds, logging level, reverse proxy rules, scrape targets).
- These settings have **nothing to do with first-run initialization** — they control *how* the service behaves while it's alive.
- **Think of it like changing a settings menu in an already-installed app**.

**Examples from your project**:
- [docker/rabbitmq/rabbitmq.conf](docker/rabbitmq/rabbitmq.conf):
  - `vm_memory_high_watermark.relative = 0.6` — How much RAM RabbitMQ may use **before it starts paging messages to disk**.
  - `disk_free_limit.absolute = 2GB` — Stop accepting messages if host disk has less than 2GB free.
  - `log.console.level = info` — Verbosity of logs.
- [docker/prometheus/prometheus.yml](docker/prometheus/prometheus.yml):
  - `scrape_interval: 15s` — How often to poll metrics targets.
  - Lists which containers to monitor (qdrant, node-exporter, postgres-exporter).
- [docker/nginx/default.conf](docker/nginx/default.conf):
  - `client_max_body_size 2000000M` — Max upload size.
  - `proxy_pass http://fastapi:8080` — Where to forward incoming HTTP requests.

**Key trait**: Just restart the container (no need to *recreate*) after editing:
```bash
docker compose -f docker-compose.yml restart prometheus
```

---

### Side-by-Side Cheat Sheet
| Feature | Docker `.env` Files | Mounted `.conf`/`.yml` Files |
|---------|--------------------|-------------------------------|
| **When read** | Container creation (first-boot setup) | Every container start / runtime reload |
| **Applies to** | Container process environment + image first-run scripts | Service internal configuration parser |
| **Purpose** | Identity & bootstrap (users, vhosts, ports, passwords) | Tuning & rules (memory, disk, routes, logging, targets) |
| **Change requires** | `--force-recreate` | Simple `restart` |
| **Location in project** | `docker/env/.env.*` (key=value format) | `docker/<service>/*.conf`, `*.yml` (service-specific format) |
| **Examples from your project** | `RABBITMQ_DEFAULT_USER`, `REDIS_PORT`, `POSTGRES_DB` | `vm_memory_high_watermark`, `scrape_interval`, `client_max_body_size` |
