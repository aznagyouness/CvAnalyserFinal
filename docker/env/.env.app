APPNAME ="essai-for-celery"
APPVERSION ="0.1.0"
APPDESCRIPTION ="A FastAPI application with Celery integration."
APP_AUTHOR ="AZNAG YOUNESS"
APP_AUTHOR_EMAIL =""

# ========================= General Config =========================
# ========================= File Config =========================
FILE_ALLOWED_TYPES=["text/plain", "application/pdf"]
FILE_MAX_SIZE=100 # MB
FILE_DEFAULT_CHUNK_SIZE_FOR_UPLOAD=1048576 # 1 MB

# ========================= chunk Config =========================
CHUNK_SIZE=3024 # 1024 characters
CHUNK_OVERLAP=128 # 128 characters

# ========================= Celery Task Queue Config =========================
CELERY_BROKER_URL="amqp://minirag_user:minirag_rabbitmq_0000@rabbitmq:5821/minirag_vhost"
CELERY_RESULT_BACKEND_URL="redis://:minirag_redis_2222@redis:6426/0"
CELERY_TASK_SERIALIZER="json"
CELERY_TASK_TIME_LIMIT=600
CELERY_TASK_ACKS_LATE=false
CELERY_WORKER_CONCURRENCY=8


# ========================= Database Config =========================


# PostgreSQL Config
POSTGRES_DATABASE_URL=postgresql+asyncpg://postgres1:postgres_password1@pgvector:5432/essai_for_celery_db





# ========================= LLM Config =========================
GENERATION_BACKEND = "OPENAI"
EMBEDDING_BACKEND = "COHERE"

# ========================= API Keys Config =========================
# OpenAI and Cohere API keys
OPENAI_API_KEY="sk-"
OPENAI_API_URL=
COHERE_API_KEY="m8-"


GENERATION_MODEL_ID_LITERAL = ["gpt-4o-mini", "gpt-4o"]
GENERATION_MODEL_ID="gpt-4o-mini"
EMBEDDING_MODEL_ID="embed-multilingual-light-v3.0"
EMBEDDING_MODEL_SIZE=384

    
INPUT_DAFAULT_MAX_CHARACTERS=1024
GENERATION_DAFAULT_MAX_TOKENS=200
GENERATION_DAFAULT_TEMPERATURE=0.1


# ========================= Vector DB Config =========================
VECTOR_DB_BACKEND_LITERAL = ["QDRANT", "PGVECTOR"]
VECTOR_DB_BACKEND = "PGVECTOR"
VECTOR_DB_PATH = "qdrant_db"
VECTOR_DB_DISTANCE_METHOD = "cosine"
VECTOR_DB_PGVEC_INDEX_THRESHOLD = 100
# to change VECTOR_DB_PGVEC_INDEX_THRESHOLD because put it in the env file


# ========================= Template Configs =========================
PRIMARY_LANG = "ar"
DEFAULT_LANG = "en"
