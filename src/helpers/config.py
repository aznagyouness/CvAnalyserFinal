from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):

    APPNAME: str
    APPVERSION: str
    APPDESCRIPTION: str
    APP_AUTHOR: str
    APP_AUTHOR_EMAIL: str


    FILE_ALLOWED_TYPES: List[str]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE_FOR_UPLOAD: int
    CHUNK_SIZE: int
    CHUNK_OVERLAP: int
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND_URL: str
    CELERY_TASK_SERIALIZER: str
    CELERY_TASK_TIME_LIMIT: int
    CELERY_TASK_ACKS_LATE: bool
    CELERY_WORKER_CONCURRENCY: int
    POSTGRES_DATABASE_URL: str


    

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



    GENERATION_MODEL_ID_LITERAL: List[str] = None
    GENERATION_MODEL_ID: str = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_SIZE: int = None
    INPUT_DAFAULT_MAX_CHARACTERS: int = None
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
