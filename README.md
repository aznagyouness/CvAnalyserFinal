# 🚀 CvAnalyser - AI-Powered CV Analysis Platform

An intelligent, enterprise-grade platform for analyzing and processing CVs using **FastAPI**, **PostgreSQL** (with pgvector), **Qdrant** (Vector DB), and **Celery** for high-performance background processing.

---

## 🌟 Key Features

- **Semantic Document Processing**: Advanced chunking and vector indexing of CVs (PDF, TXT) with **RecursiveCharacterTextSplitter**.
- **Dual-Database Architecture**: 
  - **PostgreSQL**: Relational metadata, project management, and tracking.
  - **Qdrant**: High-speed semantic search and vector retrieval via gRPC (6334) and REST (6333).
- **Two-Stage RAG Pipeline**: 
  - **Stage 1 (Retrieval)**: Fast semantic search in Qdrant.
  - **Stage 2 (Reranking) ✨**: Precision sorting using **Qwen3-Rerank** to provide the highest quality context to the LLM.
- **Multilingual Support 🌍**: YAML-based prompt templates for **English**, **Arabic**, and **French**, ensuring high-quality, localized AI responses.
- **Modular AI Architecture**: Pluggable provider system (Qwen, DeepSeek, Minimax) managed via a unified **LLMFactory**.
- **Enterprise-Grade Performance**:
  - **Resilient Embeddings**: High-throughput system with `aiolimiter` (RPM control), `asyncio.Semaphore` (concurrency), and exponential backoff retries.
  - **SQL & Vector Batching**: Optimized multi-row insertions and provider-specific batching (e.g., Qwen's 10-item limit).
- **Safety & Cost Control 🛡️**: Global limits for character input, generation tokens, and hallucination control (temperature).
- **Scalable Monitoring**: Full observability stack with Prometheus, Grafana, Node Exporter, and Postgres Exporter.

---

## 🛠 Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async Python 3.11+)
- **Vector DB**: [Qdrant](https://qdrant.tech/) (v1.17.0)
- **Relational DB**: [PostgreSQL](https://www.postgresql.org/) (with [pgvector](https://github.com/pgvector/pgvector))
- **LLM Providers**: Qwen (DashScope), DeepSeek, Minimax.
- **Task Queue**: [Celery](https://docs.celeryq.dev/) (with [RabbitMQ](https://www.rabbitmq.com/) & [Redis](https://redis.io/))
- **Monitoring**: Prometheus, Grafana, Node Exporter, Postgres Exporter.
- **Infrastructure**: [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)

---

## ⚙️ Getting Started

### 1. Setup Environment
Clone the repository and configure your environment:
```bash
cp .env.example .env.dev
```
Key variables to configure in `.env.dev`:
- `QWEN_API_KEY`: Your DashScope API key.
- `QWEN_RERANK_API_KEY`: API key for reranking support.
- `POSTGRES_DATABASE_URL`: `postgresql+asyncpg://user:pass@localhost:5432/cv_db`
- `VECTOR_DB_URL`: `http://localhost:6333`

### 2. Start Infrastructure
Launch the full production-ready stack:
```bash
docker-compose up -d
```
> **Teacher's Note**: Our `docker-compose` includes built-in healthchecks to ensure the database is ready before the app starts!

### 3. Initialize Database
Run migrations to create your SQL schema:
```bash
alembic upgrade head
```

### 4. Run the Platform
- **API Server**: `uvicorn src.main:app --reload`
- **Celery Worker**: `celery -A src.celery_app worker --loglevel=info`

---

## 🚀 API Quick Start (Production Routes)

### 1. Indexing a Project
`POST /api/v1/nlp/index/push/{project_id}`
- Synchronizes CV chunks from SQL to the Vector Database.

### 2. Semantic Search
`POST /api/v1/nlp/search/{project_id}`
- Pure retrieval to find relevant CV parts without AI generation.

### 3. Full RAG Pipeline (Ask Questions)
`POST /api/v1/nlp/answer/{project_id}`
- The complete pipeline: Search ➔ Rerank ➔ Template ➔ AI Answer.
```json
{
  "query": "What is the candidate's experience with Docker?",
  "provider": "qwen",
  "lang": "en",
  "use_reranker": true,
  "vector_db_limit": 20,
  "reranker_top_n": 5
}
```

---

## 📚 Documentation & Guides

- **[QDRANT_GUIDE.md](./QDRANT_GUIDE.md)**: Deep dive into the Vector DB, RAG pipeline, and Postman examples.
- **[ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)**: Managing SQL database migrations.

---

## 📂 Core Architecture

- **`src/llm/`**: The "AI Engine" containing providers (Qwen, DeepSeek, Minimax), the reranker, and YAML templates.
- **`src/controllers/`**: Business logic layer coordinating between data and AI services.
- **`src/vectordb/`**: Multi-provider vector database layer.
- **`src/models/`**: SQL (SQLAlchemy) and Pydantic schemas.
- **`src/routes/`**: FastAPI endpoints organized by Production and Debugging categories.

---

## 📊 Monitoring & Observability
- **Prometheus**: Metrics collection on `http://localhost:9090`.
- **Grafana**: Pre-configured dashboards on `http://localhost:3000`.
- **Flower**: Celery worker monitoring on `http://localhost:5555`.

---

## 📜 License
This project is licensed under the terms provided in the `LICENSE` file.
