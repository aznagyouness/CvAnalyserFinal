import yaml
import tiktoken
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.llm.LLMEnums import LLMRoleEnums

logger = logging.getLogger(__name__)

class RAGPromptManager:
    """
    Manages RAG prompts with versioning, i18n, and token-aware truncation.
    Optimized for DeepSeek and OpenAI-compatible chat APIs.
    """
    
    def __init__(self, lang: str = "en", prompts_dir: Optional[Path] = None):
        self.lang = lang
        if prompts_dir is None:
            # Look for prompts in a subdirectory named 'prompts' relative to this file
            self.prompts_dir = Path(__file__).parent / "prompts"
        else:
            self.prompts_dir = prompts_dir
            
        self._load_prompts()
        # Tokenizer for context window estimation (DeepSeek uses same as OpenAI)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to load tokenizer: {e}. Falling back to character counting.")
            self.tokenizer = None

    def _load_prompts(self):
        """Load prompts from YAML file based on language."""
        prompt_file = self.prompts_dir / f"{self.lang}.yaml"
        if not prompt_file.exists():
            # Fallback to English if the requested language doesn't exist
            logger.warning(f"Prompt file not found for {self.lang}, falling back to 'en'.")
            prompt_file = self.prompts_dir / "en.yaml"
            
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            self.version = data.get("version", "unknown")
            self.system_template = data.get("system", "").strip()
            self.document_template = data.get("document", "").strip()
            self.footer_template = data.get("footer", "").strip()
            self.no_docs_footer_template = data.get("no_docs_footer", self.footer_template).strip()
        except Exception as e:
            logger.error(f"Error loading prompt file {prompt_file}: {e}")
            # Minimal hardcoded defaults if file loading fails
            self.version = "fallback"
            self.system_template = "You are a helpful assistant."
            self.document_template = "Document {doc_num}: {chunk_text}"
            self.footer_template = "Question: {query}"
            self.no_docs_footer_template = "Question: {query}"

    def _count_tokens(self, text: str) -> int:
        """Helper to count tokens accurately or estimate via characters."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        
        # Fallback estimation:
        # English: ~4 chars per token
        # Arabic/Multilingual: ~1-2 chars per token
        # We use a conservative 2.0 chars per token to avoid context overflow
        return len(text) // 2 

    def format_system(self) -> str:
        """Returns the system prompt."""
        return self.system_template

    def format_document(self, doc_num: int, chunk_text: str, source: Optional[str] = None) -> str:
        """Formats a single retrieved document chunk."""
        source_line = f"### Source: {source}" if source else ""
        return self.document_template.format(
            doc_num=doc_num,
            source_line=source_line,
            chunk_text=chunk_text.strip()
        )

    def format_footer(self, query: str, has_docs: bool = True) -> str:
        """Formats the query section of the prompt."""
        if has_docs:
            return self.footer_template.format(query=query.strip())
        return self.no_docs_footer_template.format(query=query.strip())

    def build_messages(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        max_input_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """
        Constructs a message list for ChatCompletion.
        Ensures the total prompt length stays within max_input_tokens by truncating documents.
        """
        system_content = self.format_system()
        
        # Format the footer first to see how much space remains
        footer_content = self.format_footer(query, has_docs=bool(documents))
        
        system_tokens = self._count_tokens(system_content)
        footer_tokens = self._count_tokens(footer_content)
        
        # Reserved space for non-document content
        reserved_tokens = system_tokens + footer_tokens + 100 # safety buffer
        available_for_docs = max_input_tokens - reserved_tokens
        
        selected_docs_content = []
        if available_for_docs > 0:
            current_doc_tokens = 0
            for i, doc in enumerate(documents, start=1):
                doc_str = self.format_document(i, doc.get("text", ""), doc.get("source"))
                doc_tokens = self._count_tokens(doc_str)
                
                if current_doc_tokens + doc_tokens <= available_for_docs:
                    selected_docs_content.append(doc_str)
                    current_doc_tokens += doc_tokens
                else:
                    logger.info(f"Truncated documents for RAG prompt at index {i}")
                    break
        
        # Assemble the user content
        user_parts = []
        if selected_docs_content:
            user_parts.append("\n\n".join(selected_docs_content))
        user_parts.append(footer_content)
        
        user_content = "\n\n".join(user_parts)
        
        return [
            {"role": LLMRoleEnums.SYSTEM.value, "content": system_content},
            {"role": LLMRoleEnums.USER.value, "content": user_content}
        ]
