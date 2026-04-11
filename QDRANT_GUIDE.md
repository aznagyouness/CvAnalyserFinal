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

### 1.1 Disconnecting (Cleaning Up 🧹)
It is important to close the client when your application or test is finished. This releases network resources and prevents "leaking" connections.

```python
# Modern way to close
await client.close()
```

**Teacher's Tip**: If you are using FastAPI, you usually initialize the client once at startup and close it once at shutdown. In a test script, always use a `try...finally` block:

```python
client = AsyncQdrantClient(...)
try:
    # Do your work
    await client.get_collections()
finally:
    # Always runs, even if there's an error!
    await client.close()
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

## 🤖 7. Testing the LLM (Multi-Provider Support)

We have upgraded our LLM module to support multiple providers (**DeepSeek**, **qwen**, and **Minimax**) via a unified **LLMFactory**. You can test them using `src/routes/llm_test.py`.

### Supported Providers
- `"provider": "deepseek"` 
- `"provider": "qwen"` (Default)
- `"provider": "minimax"`

### Example Postman Requests

#### 1. Standard Generation
**POST** `/test/llm/generate`
```json
{
  "provider": "qwen",
  "prompt": "Hello qwen! What are your capabilities?",
  "chat_history": []
}
```

#### 2. RAG-Based Generation (The Core of AI Search)
This is where the magic happens! You send your query **plus** the documents you found in Qdrant. The AI uses the documents to answer your question accurately.

**POST** `/test/llm/rag-generate`
```json
{
  "provider": "qwen",
  "prompt": "What is the candidate's name?",
  "documents": [
    {
      "text": "The candidate name is John Doe, a senior engineer.",
      "source": "cv_john_doe.pdf"
    }
  ],
  "lang": "en",
  "temperature": 0.5
}
```

#### 3. Embedding Generation
**POST** `/test/llm/embed`
```json
{
  "provider": "qwen",
  "text": "This is a test string for qwen embedding."
}
```

---

## 🚀 8. Production API (Data Endpoints)

Before you can perform AI search (NLP), you must first **upload** your files and **chunk** them into smaller pieces. These endpoints in `src/routes/data.py` handle the raw data flow.

### 1. Uploading Files (Ingestion)
This endpoint handles the physical upload of your CVs (PDF, TXT) to the server and registers them in the PostgreSQL `assets` table.

**POST** `/api/v1/data/upload/{project_id}`
- **Function Name**: `upload_project_files`
- **Description**: Uploads one or multiple files concurrently.
- **Body**: `form-data` with a `files` key containing your documents.
- **Teacher's Note**: It automatically creates a unique filename and saves it in `assets/files/{project_id}/`.

### 2. Chunking Documents (Transformation)
Once the files are uploaded, you must "split" them into smaller parts (chunks) so the AI can read them efficiently.

**POST** `/api/v1/data/process/{project_id}`
- **Function Name**: `chunk_project_assets`
- **Description**: Loads the documents, splits them into pieces (e.g., 1000 characters), and saves them in the PostgreSQL `chunks` table.
- **Body**:
```json
{
  "file_name": null, 
  "chunk_size": 1000,
  "overlap_size": 200,
  "do_reset": 1
}
```
> **Teacher's Tip**: Set `do_reset: 1` if you want to delete old chunks for this project and start fresh!

---

## 🚀 9. Production API (NLP Endpoints)

While the `/test/llm` routes are for quick experiments, the `/api/v1/nlp` routes are the **Production-Ready** endpoints. These connect your SQL database (Postgres) with your Vector database (Qdrant) and your LLM providers.

### 1. Indexing a Project (Push to Vector DB)
Before you can search, you must "push" your CV chunks from the SQL database into Qdrant.

**POST** `/api/v1/nlp/index/push/{project_id}`
- **Description**: Fetches all chunks for a project and generates embeddings for them.
- **Body**:
```json
{
  "do_reset": 1, 
  "provider": "qwen"
}
```
> **Teacher's Note**: Use `do_reset: 1` if you want to clear the old collection and start fresh!

### 2. Semantic Search (Pure Retrieval)
Find the most relevant CV parts without generating an AI answer.

**POST** `/api/v1/nlp/search/{project_id}`
- **Body**:
```json
{
  "text": "Experience with Python and FastAPI",
  "limit": 5,
  "provider": "qwen"
}
```

### 3. The Full RAG Pipeline (Ask Questions)
The most powerful endpoint! It searches Qdrant, builds a prompt, and generates a natural language answer.

**POST** `/api/v1/nlp/answer/{project_id}`
- **Description**: Performs Search + RAG Generation in one call.
- **Body**:
```json
{
  "query": "Does this candidate have experience with Docker?",
  "provider": "qwen",
  "lang": "en",
  "limit": 5,
  "chat_history": []
}
```
- **Response**: Returns the `answer` string and the list of `retrieved_documents` used.

---

## 🎓 10. Mastering Prompt Templates (YAML)

Welcome to the most important part of "Engineering" in Prompt Engineering! In this project, we don't hardcode prompts inside our Python files. Instead, we use **YAML templates**.

### 1. Why use YAML? (The Teacher's Philosophy)
Imagine you want to change the tone of your assistant from "Professional" to "Friendly."
- **Bad Way**: Search through 50 Python files, find every string, and change them. (Messy!)
- **The Best Way**: Open one YAML file, change the `system` message, and you're done! (Clean 💎).

### 2. Where are they located?
Look in `src/llm/templates/prompts/`. You will see:
- `en.yaml` (English)
- `ar.yaml` (Arabic)
- `fr.yaml` (French)

### 3. How the "Magic" works
When you call `rag-generate` with `"lang": "ar"`, our `RAGPromptManager` does this:
1.  **Selection**: It looks for `ar.yaml`.
2.  **Loading**: It reads the templates using the `yaml` library.
3.  **Filling**: It takes your documents and "injects" them into the placeholders.

#### 🎓 Teacher's Example: The Loading Code
Here is a simplified version of how we extract the data from your YAML files in Python:

```python
import yaml
from pathlib import Path

def load_my_prompt(lang="en"):
    # 1. Path to your YAML file
    prompt_path = Path("src/llm/templates/prompts") / f"{lang}.yaml"
    
    # 2. Open and Load
    with open(prompt_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    
    # 3. Access the data like a Dictionary!
    system_personality = data.get("system")
    doc_structure = data.get("document")
    
    return system_personality, doc_structure

# Now you can use them!
personality, structure = load_my_prompt("ar")
print(f"The AI is now: {personality}")
```

#### 🎓 Teacher's Example: Filling the Variables
Once you have the template from the YAML, you need to "fill" the variables like `{doc_num}` and `{text}`. In Python, we use the `.format()` method for this.

```python
# 1. Get the template from YAML (as shown above)
document_template = "## Document No: {doc_num}\n{source}\n### Content:\n{text}"

# 2. Your real data from Qdrant
real_doc_number = 1
real_source = "### Source: cv_youness.pdf"
real_content = "John Doe is a Senior Developer with 10 years of experience."

# 3. The Injection (The Magic Step ✨)
filled_document = document_template.format(
    doc_num=real_doc_number, 
    source=real_source,
    text=real_content
)

print(filled_document)
# Output:
# ## Document No: 1
# ### Source: cv_youness.pdf
# ### Content:
# John Doe is a Senior Developer with 10 years of experience.
```

**Why this is powerful**: You can loop through 100 documents and use the same template to format all of them perfectly!

### 4. Anatomy of a Template File
Open `en.yaml` and you'll see four main sections:

1.  **`system`**: The "Personality" of the AI. It tells the model *how* to behave (e.g., "You are a helpful assistant...").
2.  **`document`**: The "Structure" of the context. It tells the AI *how* to read your data.
    - **Teacher's Secret**: We use placeholders like `{doc_num}` and `{text}`. These are variables that our Python code fills in automatically for every chunk found in Qdrant!
3.  **`footer`**: The "Call to Action". It places your question at the very end of the prompt so the AI doesn't forget it.
4.  **`no_docs_footer`**: The "Safety Net". If Qdrant finds nothing, this tells the AI to politely say "I don't know" instead of making things up (hallucinating).

### 5. How to add a New Language (e.g., Spanish 🇪🇸)
It's as easy as 1-2-3:
1.  Create a new file: `src/llm/templates/prompts/es.yaml`.
2.  Copy the content of `en.yaml`.
3.  Translate the text (but **DO NOT** change the variables like `{doc_num}`, `{source}`, or `{query}`).
4.  Now you can call your API with `"lang": "es"`!

---
*Ready to build the future? Check your `welcome_vectordb` route to see this in action!*
