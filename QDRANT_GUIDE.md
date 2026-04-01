# 🚀 Mastering Qdrant: The Vector Database Revolution

Welcome, student! If you understand **PostgreSQL**, you know how to find data by *exact matches*. But if you want to find data by **meaning**, you need **Qdrant**.

---

## 🧠 1. The Big Picture: Why Qdrant?

Imagine a library with 1 million books:
*   **Postgres (Relational)**: "Find me the book with the exact title 'Python Basics'." (Very fast).
*   **Qdrant (Vector DB)**: "Find me books that *feel* like they are about coding for beginners, even if they don't say 'Python' in the title." (Semantic search).

Qdrant stores **Embeddings** (lists of numbers like `[0.12, -0.5, 0.8...]`) that represent the "flavor" or "meaning" of your text.

---

## 🏗️ 2. The Four Pillars of Qdrant

### 1. Collections (The "Tables")
A Collection is like a table in Postgres. It holds a group of similar items (e.g., "CV_Chunks").
*   **Rule**: All items in a collection must have the same vector size (e.g., 1536 for OpenAI).

### 2. Points (The "Rows")
A Point is a single entry in your collection. It consists of:
*   **ID**: A unique number or UUID.
*   **Vector**: The "meaning" (coordinates).
*   **Payload**: The "metadata" (JSON like `{"name": "youness", "project_id": 11}`).

### 3. Distance Metrics (The "Ruler")
How do we know two things are similar? We measure the distance between their vectors:
*   **Cosine**: Measures the *angle* (Best for text/meaning).
*   **Euclidean**: Measures the *straight-line distance* (Best for images/colors).

---

## 💻 3. Learning Through Your Code

In your `src/routes/welcome.py`, we perform the **Big Five** operations:

### 1. Initialization
We use `AsyncQdrantClient` for speed. We use port `6333` for the "brain" and `6334` (gRPC) for "heavy lifting."

```python
from qdrant_client import AsyncQdrantClient

client = AsyncQdrantClient( 
    url="http://localhost:6333", # The entry point (REST)
    prefer_grpc=True,            # The speed switch (Automatic gRPC on 6334)
    timeout=30 
)
```

#### 🎓 Teacher's Secret: Which Port to Use? (6333 vs 6334)
Students often ask: *"If 6334 is for speed, why do we put 6333 in the URL?"*

Think of it like this:
- **Port 6333 (REST)** is the **Reception Desk**. You must check in here first. It speaks "Web language" (HTTP).
The client first connects to the REST API on port 6333 to verify the connection, check collection metadata, and confirm the server is alive.
- **Port 6334 (gRPC)** is the **Loading Dock**. This is where the heavy cargo (your vectors) moves. It speaks "Binary language."
The client then moves all the heavy work to the Loading Dock (6334) for speed.

**The Magic**: When you set `prefer_grpc=True`, you tell the client: *"Start at the Reception Desk (6333) to say hello, but then automatically move all the heavy work to the Loading Dock (6334)."* 

**Warning**: If you put `6334` directly in the `url` parameter, the client will try to speak "Web language" to a "Binary port," and your app will crash! Always use `6333` in the URL.

##### Why not put 6334 in the URL?
If you change the URL to http://localhost:6334 , the client will likely fail to initialize. This is because:

- Port 6334 speaks a "binary language" (gRPC).
- The url parameter starting with http:// expects the "web language" (REST).
- If you try to speak "web" to a "binary" port, the handshake will crash.

### 2. Creating a Collection
```python
await client.create_collection(
    collection_name="my_docs",
    vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE)
)
```

### 3. Upserting (Inserting/Updating)

#### 3.1 Simple Insertion
Best for adding a single new point (row) to your collection.

```python
await client.upsert(
    collection_name="my_docs",
    points=[
        models.PointStruct(
            id=1, 
            vector=[0.1] * 1536, 
            payload={"name": "youness", "role": "admin"}
        )
    ]
)
```

#### 3.2 Batch Insertion (Pro Level 🚀)
When you have 1,000s of chunks, do **not** insert them one-by-one! Use Batch Insertion to send everything in a single network request.

**Why is it important?**
- **Network Efficiency**: Reduces the overhead of 1,000s of HTTP/gRPC calls.
- **Speed**: It is 10x - 50x faster than single inserts.
- **Atomicity**: Qdrant handles the batch as a more efficient internal operation.

```python
from qdrant_client.http import models

# Prepare a list of points
points = [
    models.PointStruct(
        id=i, 
        vector=[0.1] * 1536, 
        payload={"chunk_id": i, "text": f"Chunk number {i}"}
    )
    for i in range(100)
]

# Send them all at once!
await client.upsert(
    collection_name="my_docs",
    points=points,
    wait=True  # Ensure the data is processed before moving on
)
```

### 4. Searching (The Modern Way 🎯)
This is the magic! You give it a vector, and it finds the closest neighbors. We use `query_points` as it is the most robust and modern API.

```python
results = await client.query_points(
    collection_name="my_docs",
    query=[0.1] * 1536,  # The "meaning" you're looking for
    limit=5,             # Top 5 most similar results
    with_payload=True    # Bring back the metadata too!
)

for hit in results.points:
    print(f"ID: {hit.id}, Score: {hit.score}, Metadata: {hit.payload}")
```

### 5. Pro Level: Filtering with Payloads 🎯
In a real app, you don't want to search *all* documents. You want to search only documents belonging to a specific project. 

```python
from qdrant_client.http import models

results = await client.query_points(
    collection_name="my_docs",
    query=[0.1] * 1536,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="project_id", 
                match=models.MatchValue(value=11)
            )
        ]
    ),
    limit=3
)
```

### 6. Pro Level: The Scroll API 📜
Sometimes you don't want to "search" by meaning; you just want to "list" all points (like `SELECT *` in SQL). You use `scroll` for this.

```python
points, next_page_offset = await client.scroll(
    collection_name="my_docs",
    limit=10,
    with_payload=True,
    with_vectors=False # Don't download vectors unless you need them (saves bandwidth)
)
```

---

## 🎓 4. Teacher's Pro-Tips

1.  **Payload Indexing**: If you filter by `project_id` frequently, you **must** create a payload index to keep it fast!
    ```python
    await client.create_payload_index(
        collection_name="my_docs",
        field_name="project_id",
        field_schema=models.PayloadSchemaType.INTEGER
    )
    ```
2.  **Memory**: Qdrant is built in **Rust**. It is incredibly fast and memory-efficient.
3.  **Persistence**: Even if your Docker container restarts, Qdrant keeps your data safe in its `/storage` folder.

---

## 🧪 5. Testing and Verification

### 1. Version Compatibility Check
**🎓 Teacher's Warning**: Ensure your Qdrant client version matches your server version in `docker-compose.yml`.
- If your client (e.g., `1.17.0`) is ahead of the server (e.g., `1.13.6`), you might see warnings. 
- We have set `check_compatibility=False` in our provider to handle this, but for production, always aim for matching versions!

### 2. Finding Your Data (Where are my vectors?)
You have two main ways to see what you've inserted:

#### **A. Qdrant Dashboard (Visual & Recommended)**
Qdrant has a built-in web interface to browse your collections, points, and payloads.
- **URL**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **What to do**:
  1. Click on your collection (e.g., `test_cv`).
  2. View the list of **"Points"**.
  3. Click a point to see its **Payload** (text/metadata) and its **Vector** (the coordinates).

#### **B. Using the Test API (The "Scroll" Method)**
If you want to retrieve data via Postman, use the **Scroll API** (like `SELECT *` in SQL). We've added this to your test suite:
- **Endpoint**: `GET http://localhost:8000/test/qdrant/collection/test_cv/points`
- **Result**: Returns points with their payloads and vectors in JSON format.

---

## 🚀 6. Postman Test Suite Walkthrough

We have built a dedicated testing suite in `src/routes/qdrant_test.py` to help you verify everything is working.

### 1. The Connection Check
**URL**: `POST http://localhost:8000/test/qdrant/connect`
*   **Goal**: Verify your FastAPI app can talk to the Qdrant Docker container.

### 2. Collection Management
*   **Create**: `POST http://localhost:8000/test/qdrant/create-collection`
    ```json
    { "collection_name": "test_cv", "embedding_size": 3 }
    ```
*   **List All Collections**: `GET http://localhost:8000/test/qdrant/collections`
*   **Delete**: `DELETE http://localhost:8000/test/qdrant/collection/test_cv`

### 3. Data Insertion (Points)
*   **Insert Many (Batch)**: `POST http://localhost:8000/test/qdrant/insert-many`
    ```json
    {
       "collection_name": "test_cv", 
       "texts": ["Hello world", "Qdrant is fast"], 
       "vectors": [[0.1,0.3,0.3], [0.3,0.3,0.3]], 
       "record_ids": [1, 2] 
    }
    ```
    *   **🎓 Teacher's Warning**: Remember that `record_ids` must be **integers** or **UUIDs**. Strings like `"id1"` will fail!

### 4. Search
*   **Search**: `POST http://localhost:8000/test/qdrant/search`
    ```json
    {
       "collection_name": "test_cv",
       "vector": [0.1,0.3,0.3],
       "limit": 5
    }
    ```

---

## 🤖 7. Testing the LLM (DeepSeek)

We have also added a dedicated suite for testing the DeepSeek model and RAG prompts in `src/routes/llm_test.py`.

### 1. Basic Text Generation
**URL**: `POST http://localhost:8000/test/llm/generate`
```json
{
  "prompt": "Hello, how can you help me today?",
  "temperature": 0.7
}
```

### 2. RAG-Based Generation (With Documents)
**URL**: `POST http://localhost:8000/test/llm/rag-generate`
```json
{
  "prompt": "What is the candidate's name?",
  "documents": [
    {"text": "Candidate name is John Doe, a senior Python developer.", "source": "cv_john.pdf"}
  ],
  "lang": "en"
}
```

### 3. Text Embedding
**URL**: `POST http://localhost:8000/test/llm/embed`
```json
{
  "text": "This is a test string for embedding."
}
```

---
*Ready to build the future? Check your `welcome_vectordb` route to see this in action!*
