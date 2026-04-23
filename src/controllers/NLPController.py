from src.controllers.BaseController import BaseController
from src.models.db_schemes.cv_analysis_db.db_tables import DataChunk, Project
from src.llm import LLMFactory, LLMProviderEnums, LLMModelEnums
from src.llm.templates.rag_prompt import RAGPromptManager
from src.helpers.config import get_settings
from typing import List, Optional, Dict, Any
import json
import logging
import time



settings = get_settings()

class NLPController(BaseController):

    def __init__(self, vectordb_client=None,llm_client=None):
        super().__init__()
        self.vectordb_client = vectordb_client      
        self.llm_client = llm_client
        # like llm = LLMFactory.get_llm(provider=provider)
        self.logger = logging.getLogger(__name__)
        self.project_id = None

    def set_project_id(self, project_id: str):
        self.project_id = project_id

    def create_collection_name(self, project_id: Optional[int] = None):
        pid = project_id if project_id is not None else self.project_id
        return f"collection_{pid}".strip()
    
    async def reset_vector_db_collection(self, project_id: int):
        collection_name = self.create_collection_name(project_id=project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self, project_id: int):
        collection_name = self.create_collection_name(project_id=project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    async def index_into_vector_db(self, project_id: int, chunks: List[DataChunk],
                                   do_reset: bool = False,
                                   provider: str = LLMProviderEnums.QWEN.value):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project_id)

 
        # step2: get embedding client
        #llm = LLMFactory.get_llm(provider=provider)
        self.llm_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

        # step3: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        
        # Async embed
        vectors = await self.llm_client.embed_text(text=texts)

        # step4: create collection if not exists
        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.llm_client.embedding_size,
            do_reset=do_reset if do_reset else False,
        )

        # step5: insert into vector db
        record_ids = [ c.chunk_id for c in chunks ]
        _ = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=record_ids,
        )

        return True

    async def search_vector_db_collection(self, project_id: int, text: str, limit: int = 10,
                                         provider: str = LLMProviderEnums.DEEPSEEK.value):

        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project_id)

        # step2: get embedding client
        #llm = LLMFactory.get_llm(provider=provider)
        #llm.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

        # step3: get text embedding vector
        vectors = await self.llm_client.embed_text(text=text)

        if not vectors or len(vectors) == 0:
            return False
        
        query_vector = vectors # If single string, embed_text returns single vector

        # step4: do semantic search
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        if not results:
            return False

        return results
    
    async def answer_rag_question(self, project_id: int, query: str, limit: int = 10,
                                 provider: str = LLMProviderEnums.QWEN.value,
                                 lang: str = "en",
                                 chat_history: List[dict] = []):
        
        start = time.time()

        # step1: retrieve related documents
        retrieved_documents = await self.search_vector_db_collection(
            project_id=project_id,
            text=query,
            limit=limit,
            provider=provider
        )

        end_time = time.time()
        print(f"Retrieved {len(retrieved_documents)} documents in {end_time - start} seconds")

        if not retrieved_documents or len(retrieved_documents) == 0:
            return "I couldn't find any relevant information to answer your question.", [], []
        
        # step2: get generation client
        #llm = LLMFactory.get_llm(provider=provider)
        #llm.set_generation_model(settings.GENERATION_MODEL_ID)

        # step3: prepare documents for RAG
        documents = []
        for doc in retrieved_documents:
            documents.append({
                "text": doc.text,
                "source": doc.metadata.get("source", "Unknown")
            })

        # step4: get prompt for debugging
        prompt_manager = RAGPromptManager(lang=lang)
        messages = prompt_manager.build_messages(
            query=query,
            documents=documents
        )
        
        full_history = list(chat_history) + messages

        start = time.time()

        # step5: generate answer
        answer = await self.llm_client.generate_text(
            prompt=query,
            documents=documents,
            chat_history=chat_history,
            lang=lang
        )

        end_time = time.time()
        print(f"Generated answer in {end_time - start} seconds")

        return answer, full_history, retrieved_documents
