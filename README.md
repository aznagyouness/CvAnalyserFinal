# 🚀 CvAnalyser - AI-Powered CV Analysis Platform

An intelligent, enterprise-grade platform for analyzing and processing CVs using **FastAPI**, **PostgreSQL** (with pgvector), **Qdrant** (Vector DB), and **Celery** for high-performance background processing.

---

## 🌟 Key Features

- **Semantic Document Processing**: Advanced chunking and vector indexing of CVs (PDF, TXT).
- **Dual-Database Architecture**: 
  - **PostgreSQL**: Relational metadata, project management, and tracking.
  - **Qdrant**: High-speed semantic search and vector retrieval.
- **RAG (Retrieval-Augmented Generation)**: AI-powered question answering using top-tier LLMs (Qwen, DeepSeek, Minimax).
- **Pro-Level Performance**:
  - **SQL Batching**: Optimized multi-row insertions for chunks.
  - **LLM Batching**: Automatic batching for embedding generation (handles API limits seamlessly).
- **Prompt Engineering**: YAML-based prompt templating for clean, maintainable AI instructions.
- **Async Workflow**: Fully asynchronous architecture from API to Database to Background Tasks.
- **Scalable Monitoring**: Integrated with Prometheus, Grafana, and Flower.

---

## 🛠 Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async Python)
- **Vector DB**: [Qdrant](https://qdrant.tech/) (High-performance search)
- **Relational DB**: [PostgreSQL](https://www.postgresql.org/) (with [pgvector](https://github.com/pgvector/pgvector))
- **LLM Integration**: [LangChain](https://www.langchain.com/) & Native Provider SDKs (Qwen, DeepSeek)
- **Task Queue**: [Celery](https://docs.celeryq.dev/) (with [RabbitMQ](https://www.rabbitmq.com/) & [Redis](https://redis.io/))
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Infrastructure**: [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)

---

## ⚙️ Getting Started

### 1. Setup Environment
Clone the repository and configure your environment:
```bash
cp .env.example .env.dev
```
*Ensure you add your `DASHSCOPE_API_KEY` (Qwen) or `DEEPSEEK_API_KEY` in the `.env` file.*

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

## � Documentation & Guides

- **[QDRANT_GUIDE.md](./QDRANT_GUIDE.md)**: Master the vector database, batching, and semantic search.
- **[ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md)**: Learn how to manage database migrations.

---

## 📂 Core Architecture

- `src/controllers/`: Business logic (Process, NLP, Project controllers).
- `src/vectordb/`: Multi-provider vector database layer (Qdrant, PGVector).
- `src/llm/`: Pluggable LLM provider system (Qwen, DeepSeek, Minimax).
- `src/models/`: Database schemas and CRUD operations.
- `src/routes/`: 
  - `/data`: Ingestion and Chunking.
  - `/nlp`: Semantic Search and RAG.

---

## 📊 Monitoring & Observability
- **Metrics**: `/metrics` (Prometheus format).
- **Worker Stats**: Flower dashboard on port `5555`.
- **Dashboards**: Grafana visualizations for system health.

---

## 📜 License
This project is licensed under the terms provided in the `LICENSE` file.
