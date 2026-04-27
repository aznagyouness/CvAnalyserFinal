# 🚀 CvAnalyser - AI-Powered CV Analysis Platform

An intelligent, enterprise-grade platform for analyzing and processing CVs using **FastAPI**, **PostgreSQL** (with pgvector), **Qdrant** (Vector DB), and **Celery** for high-performance background processing.

---

## 🌟 Key Features

- **Semantic Document Processing**: Advanced chunking and vector indexing of CVs (PDF, TXT) with **RecursiveCharacterTextSplitter**.
- **Dual-Database Architecture**: 
  - **PostgreSQL**: Relational metadata, project management, and tracking.
  - **Qdrant**: High-speed semantic search and vector retrieval via gRPC (6334) and REST (6333).
- **RAG (Retrieval-Augmented Generation)**: AI-powered question answering using top-tier LLMs (Qwen, DeepSeek, Minimax).
- **Enterprise-Grade Performance**:
  - **Resilient Embeddings**: High-throughput embedding system with `aiolimiter` (RPM control), `asyncio.Semaphore` (concurrency), and exponential backoff retries.
  - **SQL Batching**: Optimized multi-row insertions for chunks and assets.
  - **Automatic Batching**: Transparently handles LLM provider limits (e.g., Qwen's 10-item limit).
- **Async Workflow**: Fully asynchronous architecture from API to Database to Background Tasks.
- **Scalable Monitoring**: Integrated with Prometheus, Grafana, and Flower for worker observability.

---

## 🛠 Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async Python 3.10+)
- **Vector DB**: [Qdrant](https://qdrant.tech/) (High-performance search)
- **Relational DB**: [PostgreSQL](https://www.postgresql.org/) (with [pgvector](https://github.com/pgvector/pgvector))
- **LLM Integration**: [LangChain](https://www.langchain.com/) & Native Provider SDKs (OpenAI-compatible)
- **Task Queue**: [Celery](https://docs.celeryq.dev/) (with [RabbitMQ](https://www.rabbitmq.com/) & [Redis](https://redis.io/))
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Infrastructure**: [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)

---

## ⚙️ Getting Started

### 1. Setup Environment
Clone the repository and configure your environment:
```bash
cp .env.example .env
```
Key variables to configure:
- `QWEN_API_KEY`: Your DashScope/Qwen API key.
- `POSTGRES_URL`: `postgresql+asyncpg://user:pass@localhost:5432/cv_db`
- `QDRANT_URL`: `http://localhost:6333`

### 2. Start Infrastructure
Launch the full stack (Postgres, Qdrant, Redis, RabbitMQ, Prometheus, Grafana):
```bash
docker-compose up -d
```

### 3. Initialize Database
Run migrations to create your SQL schema:
```bash
alembic upgrade head
```

### 4. Run the Platform
- **API Server**: `uvicorn src.main:app --reload`
- **Celery Worker**: `celery -A src.celery_app worker --loglevel=info`

---

## 🚀 API Quick Start

### 1. Upload CVs
`POST /api/v1/data/upload/{project_id}`
- Upload multiple PDF/TXT files to a specific project.

### 2. Process & Index
`POST /api/v1/data/process/{project_id}`
- Chunks the files, generates embeddings, and pushes to Qdrant.
```json
{
  "chunk_size": 1000,
  "overlap_size": 200,
  "do_reset": true
}
```

### 3. Ask Questions (RAG)
`POST /api/v1/nlp/answer/{project_id}`
- Semantic search across CVs followed by LLM generation.
```json
{
  "query": "What are the candidate's main skills in Python?",
  "lang": "en",
  "limit": 5
}
```

---

## 📚 Documentation & Guides

- **[QDRANT_GUIDE.md](./QDRANT_GUIDE.md)**: Master the vector database, batching, and semantic search.
- **[ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)**: Learn how to manage database migrations.

---

## 📂 Core Architecture

- **`src/controllers/`**: Business logic layer (Process, NLP, Project).
- **`src/vectordb/`**: Multi-provider vector database layer (Qdrant, PGVector).
- **`src/llm/`**: Pluggable LLM provider system (Qwen, DeepSeek, Minimax).
- **`src/models/`**: SQLAlchemy schemas and CRUD operations.
- **`src/routes/`**: FastAPI endpoints organized by domain.

---

## 📊 Monitoring & Observability
- **API Metrics**: `/metrics` (Prometheus format).
- **Celery Worker**: Flower dashboard on `http://localhost:5555`.
- **Grafana**: Pre-configured dashboards for system health.

---

## 📜 License
This project is licensed under the terms provided in the `LICENSE` file.
