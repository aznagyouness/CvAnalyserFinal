from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):

    APPNAME: str
    APPVERSION: str
    APPDESCRIPTION: str
    APP_AUTHOR: str
    APP_AUTHOR_EMAIL: str
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    INFRA_LOG_LEVEL: str = "WARNING"


    FILE_ALLOWED_TYPES: List[str]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE_FOR_UPLOAD: int
    CHUNK_SIZE: int
    CHUNK_OVERLAP: int
    MAX_RPM_EMBEDDING: int
    MAX_RPM_GENERATION: int = 20 # Default if not in .env
    MAX_CONCURRENT_REQUESTS_EMBEDDING: int
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND_URL: str
    CELERY_TASK_SERIALIZER: str
    CELERY_TASK_TIME_LIMIT: int
    CELERY_TASK_ACKS_LATE: bool
    CELERY_WORKER_CONCURRENCY: int
    POSTGRES_DATABASE_URL: str
    REDIS_URL_QUOTA: str
    REDIS_URL_TASKIQ_RESULTS: str
    REDIS_URL_TASKIQ_LIMITER: str

    TASKIQ_BROKER_URL: str

    # ── Idempotency ──────────────────────────────────────────────────────────────
    # run_ttl: MUST be > p99 task runtime. 
    IDEMPOTENCY_RUN_TTL: int = 900
    # done_ttl: dedup window — within this period, a duplicate is recognized and skipped.
    IDEMPOTENCY_DONE_TTL: int = 86_400
    # strict_audit: True = task fails if Postgres audit insert fails.
    IDEMPOTENCY_STRICT_AUDIT: bool = True
    

    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: str = None
    OPENAI_API_URL: str = None
    COHERE_API_KEY: str = None
    DEEPSEEK_API_KEY: str = None
    DEEPSEEK_API_URL: str = None
    QWEN_API_KEY: str = None
    QWEN_API_URL: str = None
    MINIMAX_API_KEY: str = None
    MINIMAX_API_URL: str = None
    QWEN_RERANK_API_KEY: str = None
    QWEN_RERANK_API_URL: str = None
    QWEN_RERANK_MODEL_ID: str = "qwen3-rerank"



    GENERATION_MODEL_ID_LITERAL: List[str] = None
    GENERATION_MODEL_ID: str = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_SIZE: int = None
    MAX_INPUT_TOKENS: int = None
    GENERATION_DAFAULT_MAX_TOKENS: int = None
    GENERATION_DAFAULT_TEMPERATURE: float = None

    # added by me
    VECTOR_DB_URL: str = None
    VECTOR_DB_COLLECTION_NAME: str = None
    #note added by me 
    VECTOR_DB_BACKEND_LITERAL: List[str] = None
    VECTOR_DB_BACKEND : str
    VECTOR_DB_PATH : str
    VECTOR_DB_DISTANCE_METHOD: str = None
    VECTOR_DB_PGVEC_INDEX_THRESHOLD: int = 100

    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"

    # Pydantic Settings
    model_config = SettingsConfigDict(env_file=".env.dev")

def get_settings():
    return Settings()
