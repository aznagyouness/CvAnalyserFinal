import os
import asyncio
from openai import AsyncOpenAI
from rag_prompt import RAGPromptManager

# Initialize the prompt manager
prompt_mgr = RAGPromptManager(lang="en")

# DeepSeek client
client = AsyncOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

async def rag_query(query: str, documents: list, model: str = "deepseek-chat") -> str:
    """
    Perform a RAG query using DeepSeek.
    documents: list of dicts with keys 'text' and optionally 'source'
    """
    # Build messages with token-aware truncation
    messages = prompt_mgr.build_messages(
        query=query,
        documents=documents,
        max_total_tokens=32000,   # DeepSeek context window
        reserve_response_tokens=2048
    )

    # Call the API
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
        temperature=0.7,
        max_tokens=2048
    )
    return response.choices[0].message.content

async def main():
    # Example retrieved documents (your RAG retrieval logic would produce this)
    retrieved_docs = [
        {"text": "Paris is the capital of France. France is a country in Europe.", "source": "encyclopedia"},
        {"text": "The Eiffel Tower is located in Paris.", "source": "travel guide"}
    ]
    query = "What is the capital of France?"
    answer = await rag_query(query, retrieved_docs)
    print(answer)

    # Example with no documents
    print("\n--- No documents case ---")
    answer_no_docs = await rag_query("What is the capital of France?", [])
    print(answer_no_docs)

if __name__ == "__main__":
    asyncio.run(main())