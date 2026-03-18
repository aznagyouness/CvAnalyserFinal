from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document  # Use LangChain's official Document class
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.controllers.BaseController import BaseController
from src.controllers.ProjectController import ProjectController
from models import ProcessingEnum


class ProcessController(BaseController):
    """
    Enhanced controller for loading, splitting, and processing documents.
    Uses LangChain's document loaders and text splitters with metadata preservation.
    """

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id
        self.project_path = Path(ProjectController().get_project_path(project_id))

    def _get_file_extension(self, file_id: str) -> str:
        """Return file extension including the dot."""
        return Path(file_id).suffix

    def _get_file_loader(self, file_id: str):
        """
        Return the appropriate LangChain document loader for the given file.
        Returns None if the file does not exist or extension is unsupported.
        """
        file_path = os.path.join(
            self.project_path,
            file_id
        )
        if not file_path.exists():
            return None

        ext = self._get_file_extension(file_id)
        loaders = {
            ProcessingEnum.TXT.value: TextLoader(str(file_path), encoding="utf-8"),
            ProcessingEnum.PDF.value: PyMuPDFLoader(str(file_path)),
        }
        return loaders.get(ext)

    def load_documents(self, file_id: str) -> Optional[List[Document]]:
        """
        Load the document(s) from the given file.
        Returns a list of LangChain Document objects, or None if loading fails.
        """
        loader = self._get_file_loader(file_id)
        if loader is None:
            return None
        try:
            return loader.load()
        except Exception as e:
            # Log the error appropriately in production
            print(f"Error loading {file_id}: {e}")
            return None

    def split_documents(
        self,
        documents: List[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> List[Document]:
        """
        Split a list of LangChain Documents into smaller chunks using
        RecursiveCharacterTextSplitter. Metadata from the original documents
        is automatically copied to each chunk.
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],  # Respect paragraphs, then lines, then words
        )
        return text_splitter.split_documents(documents)

    def process_file(
        self,
        file_id: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> Optional[List[Document]]:
        """
        High-level method: load a file and split it into chunks.
        Returns a list of chunk Documents, or None if any step fails.
        """
        docs = self.load_documents(file_id)
        if docs is None:
            return None
        return self.split_documents(docs, chunk_size, chunk_overlap)