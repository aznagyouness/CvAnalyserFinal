from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from src.vectordb.VectorDBInterface import VectorDBInterface
from src.vectordb.enums.VectorDBEnums import DistanceMethodEnums
import logging
from typing import List
from src.vectordb.enums.RetrievedDocumentEnum import RetrievedDocumentEnum
from src.helpers.config import get_settings

settings = get_settings()

class QdrantDBProvider(VectorDBInterface):

    def __init__(self, db_client: str, default_vector_size: int = settings.EMBEDDING_MODEL_SIZE,
                                     distance_method: str = None, index_threshold: int=100):

        self.client = None
        self.db_client = db_client
        self.distance_method = None
        self.default_vector_size = default_vector_size

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT

        self.logger = logging.getLogger('uvicorn')

    async def connect(self):
        self.client = AsyncQdrantClient( 
                        url=settings.VECTOR_DB_URL, # The entry point (REST)
                        prefer_grpc=True,            # The speed switch (Automatic gRPC on 6334)
                        timeout=30,
                        #check_compatibility=False
                    )

    async def disconnect(self):
        # Close the client to clean up resources
        await self.client.close()

    async def is_collection_existed(self, collection_name: str) -> bool:
        return await self.client.collection_exists(collection_name=collection_name)
    
    async def list_all_collections(self) -> List:
        response = await self.client.get_collections()
        return [collection.name for collection in response.collections]
    
    async def get_collection_info(self, collection_name: str) -> dict:
        response = await self.client.get_collection(collection_name=collection_name)
        return response.model_dump()
    
    async def delete_collection(self, collection_name: str):
        if await self.is_collection_existed(collection_name):
            self.logger.info(f"Deleting collection: {collection_name}")
            return await self.client.delete_collection(collection_name=collection_name)
        
    async def create_collection(self, collection_name: str, 
                                embedding_size: int,
                                do_reset: bool = False):
        if do_reset:
            _ = await self.delete_collection(collection_name=collection_name)
        
        if not await self.is_collection_existed(collection_name):
            self.logger.info(f"Creating new Qdrant collection: {collection_name}")
            
            _ = await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method
                )
            )

            return True
        
        return False
    
    async def insert_one(self, collection_name: str, text: str, vector: list,
                         metadata: dict = None, 
                         record_id: str = None):
        
        if not await self.is_collection_existed(collection_name):
            self.logger.error(f"Can not insert new record to non-existed collection: {collection_name}")
            return False
        
        try:
            _ = await self.client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=record_id,
                        vector=vector,
                        payload={
                            "text": text, "metadata": metadata
                        }
                    )
                ],
                wait=True
            )
        except Exception as e:
            self.logger.error(f"Error while inserting record: {e}")
            return False

        return True
    
    async def insert_many(self, collection_name: str, texts: list, 
                          vectors: list, metadata: list = None, 
                          record_ids: list = None, batch_size: int = 50):
        
        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = list(range(0, len(texts)))

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size

            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_record_ids = record_ids[i:batch_end]

            batch_records = [
                models.PointStruct(
                    id=batch_record_ids[x],
                    vector=batch_vectors[x],
                    payload={
                        "text": batch_texts[x], "metadata": batch_metadata[x]
                    }
                )

                for x in range(len(batch_texts))
            ]

            try:
                _ = await self.client.upsert(
                    collection_name=collection_name,
                    points=batch_records,
                    wait=True
                )
            except Exception as e:
                self.logger.error(f"Error while inserting batch: {e}")
                return False

        return True
        
    async def search_by_vector(self, collection_name: str, vector: list, limit: int = 5) -> List[RetrievedDocumentEnum]:

        # Using query_points which is the modern and more robust API in AsyncQdrantClient
        results = await self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
            with_payload=True
        )

        if not results or not results.points:
            return []
        
        return [
            RetrievedDocumentEnum(**{
                "score": result.score,
                "text": result.payload.get("text", ""),
                "metadata": result.payload
            })
            for result in results.points
        ]

