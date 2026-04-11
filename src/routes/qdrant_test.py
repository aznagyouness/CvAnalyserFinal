from fastapi import APIRouter, HTTPException, Depends
from src.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.vectordb.enums.VectorDBEnums import VectorDBEnums
from src.helpers.config import get_settings, Settings
from typing import List, Optional, Union
from pydantic import BaseModel
from src.database import get_utils

router = APIRouter(prefix="/test/qdrant", tags=["Qdrant Testing"])

def get_qdrant_provider(settings: Settings = Depends(get_settings)):
    # Initialize factory
    factory = VectorDBProviderFactory(config=settings)
    # Create Qdrant provider using the factory
    return factory.create(provider=VectorDBEnums.QDRANT.value)

settings = get_settings()
class CollectionCreateRequest(BaseModel):
    collection_name: str
    embedding_size: int = settings.EMBEDDING_MODEL_SIZE # Default to config embedding size

class PointInsertRequest(BaseModel):
    collection_name: str
    text: str
    vector: List[float]
    metadata: Optional[dict] = None
    record_id: Union[str, int]

class BatchInsertRequest(BaseModel):
    collection_name: str
    texts: List[str]
    vectors: List[List[float]]
    metadata: Optional[List[dict]] = None
    record_ids: Optional[List[Union[str, int]]] = None

class SearchRequest(BaseModel):
    collection_name: str
    vector: List[float]
    limit: int = 5

@router.post("/connect")
async def test_connect(qdrant_provider=Depends(get_qdrant_provider)):
    try:
        await qdrant_provider.connect()
        return {"status": "success", "message": "Connected to Qdrant"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-collection")
async def test_create_collection(req: CollectionCreateRequest, qdrant_provider=Depends(get_qdrant_provider)):
    await qdrant_provider.connect()
    success = await qdrant_provider.create_collection(
        collection_name=req.collection_name,
        embedding_size=req.embedding_size,
        do_reset=True
    )
    return {"status": "success" if success else "failed", "collection": req.collection_name}

@router.get("/collections")
async def test_list_collections(qdrant_provider=Depends(get_qdrant_provider)):
    await qdrant_provider.connect()
    collections = await qdrant_provider.list_all_collections()
    return {"collections": collections}

@router.post("/insert-one")
async def test_insert_one(req: PointInsertRequest, qdrant_provider=Depends(get_qdrant_provider)):
    await qdrant_provider.connect()
    success = await qdrant_provider.insert_one(
        collection_name=req.collection_name,
        text=req.text,
        vector=req.vector,
        metadata=req.metadata,
        record_id=req.record_id
    )
    return {"status": "success" if success else "failed"}

@router.post("/insert-many")
async def test_insert_many(req: BatchInsertRequest, qdrant_provider=Depends(get_qdrant_provider)):
    await qdrant_provider.connect()
    try:
        success = await qdrant_provider.insert_many(
            collection_name=req.collection_name,
            texts=req.texts,
            vectors=req.vectors,
            metadata=req.metadata,
            record_ids=req.record_ids
        )
        if not success:
             raise HTTPException(status_code=400, detail="Insertion failed. Check logs for dimension mismatch or ID format errors.")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def test_search(req: SearchRequest, qdrant_provider=Depends(get_qdrant_provider)):
    await qdrant_provider.connect()
    results = await qdrant_provider.search_by_vector(
        collection_name=req.collection_name,
        vector=req.vector,
        limit=req.limit
    )
    return {"results": results}

@router.delete("/collection/{name}")
async def test_delete_collection(name: str, qdrant_provider=Depends(get_qdrant_provider)):
    await qdrant_provider.connect()
    await qdrant_provider.delete_collection(collection_name=name)
    return {"status": "success", "message": f"Collection {name} deleted"}


@router.get("/collection/{name}/points")
async def test_list_points(name: str, limit: int = 10, qdrant_provider=Depends(get_qdrant_provider)):
    await qdrant_provider.connect()
    # Scroll retrieves points without a search query
    points, _ = await qdrant_provider.client.scroll(
        collection_name=name,
        limit=limit,
        with_payload=True,
        with_vectors=True  # Set to True to see the actual numbers
    )
    return {"points": points}
