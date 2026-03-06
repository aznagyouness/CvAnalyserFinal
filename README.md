# CvAnalyser - AI-Powered CV Analysis Platform

An intelligent platform for analyzing and processing CVs using FastAPI, PostgreSQL (with pgvector), SQLAlchemy, and Celery for background processing.

## 🚀 Features
- **CV Upload & Processing**: Support for multiple file formats (PDF, Text).
- **Asynchronous Processing**: Background tasks handled by Celery with RabbitMQ and Redis.
- **Relational Data Management**: PostgreSQL for storing project, asset, and chunk metadata.
- **Scalable Architecture**: Dockerized components for easy deployment and monitoring.
- **Monitoring**: Integrated with Prometheus and Grafana for system and application metrics.

---

## 🛠 Tech Stack
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: [PostgreSQL](https://www.postgresql.org/) (with [pgvector](https://github.com/pgvector/pgvector) for future vector search)
- **ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Task Queue**: [Celery](https://docs.celeryq.dev/)
- **Brokers/Backends**: [RabbitMQ](https://www.rabbitmq.com/), [Redis](https://redis.io/)
- **Containerization**: [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- **Observability**: [Prometheus](https://prometheus.io/), [Grafana](https://grafana.com/), [Flower](https://flower.readthedocs.io/)

---

## ⚙️ Prerequisites
- Python 3.10+
- Docker & Docker Compose
- WSL2 (if running on Windows)

---

## 🚀 Getting Started

### 1. Setup Environment
Clone the repository and create a `.env` file based on your project configuration. Ensure you have your API keys for LLM services (OpenAI/Cohere) if applicable.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start Infrastructure (Docker)
Run the required services (Postgres, RabbitMQ, Redis, etc.):
```bash
docker-compose up -d
```

### 4. Database Migrations
Initialize and update your database schema:
```bash
alembic upgrade head
```
*(Refer to [ALEMBIC_GUIDE.md](./ALEMBIC_GUIDE.md) for detailed migration instructions.)*

### 5. Run the Application
Start the FastAPI server:
```bash
uvicorn src.main:app --reload
```

### 6. Run Celery Worker
In a separate terminal:
```bash
celery -A src.celery_app worker --loglevel=info
```

---

## 📂 Project Structure
- `src/`: Main source code.
  - `controllers/`: Business logic.
  - `models/`: Database schemas (PostgreSQL & MongoDB) and CRUD operations.
  - `routes/`: API endpoints.
  - `tasks/`: Celery background tasks.
- `alembic/`: Database migration scripts.
- `docker/`: Docker configurations and environment files.
- `file lihgtining/`: Specialized AI processing modules (MiniCPM experiments).

---

## 📊 Monitoring
- **FastAPI Metrics**: Available at `/metrics`.
- **Flower (Celery Monitoring)**: Check your local Flower instance (typically on port 5555).
- **Grafana Dashboards**: Access metrics visualizations via your Grafana container.

---

## 📜 License
This project is licensed under the terms provided in the `LICENSE` file (if available).
