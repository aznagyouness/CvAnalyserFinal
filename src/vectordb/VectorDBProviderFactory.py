from src.vectordb.providers import QdrantDBProvider, PGVectorProvider
from src.vectordb.enums.VectorDBEnums import VectorDBEnums
from src.controllers.BaseController import BaseController


class VectorDBProviderFactory:
    """
    - return an instance created of VectorDBProvider based on the provider type
    - provider type: QDRANT, PGVECTOR
    - db client: 
            - async_sessionmaker instance or None for PGVECTOR provider.
            - AsyncQdrantClient instance or None for QDRANT provider.
    """
    def __init__(self, config, db_client = None):
        self.config = config
        self.base_controller = BaseController()
        self.db_client = db_client

    def create(self, provider: str):
        if provider == VectorDBEnums.QDRANT.value:
            qdrant_db_client = self.base_controller.get_database_path(db_name=self.config.VECTOR_DB_PATH)

            return QdrantDBProvider(
                db_client=qdrant_db_client,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                index_threshold=self.config.VECTOR_DB_PGVEC_INDEX_THRESHOLD,
            )
        
        if provider == VectorDBEnums.PGVECTOR.value:
            return PGVectorProvider(
                db_client=self.db_client,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                index_threshold=self.config.VECTOR_DB_PGVEC_INDEX_THRESHOLD,
            )
        
        return None
