from pathlib import Path
from typing import List, Optional
import os

from langchain_core.documents import Document  # Use LangChain's official Document class
from langchain_community.document_loaders import TextLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.controllers.BaseController import BaseController
from src.controllers.ProjectController import ProjectController
from src.models.enums.ProcessingEnum import ProcessingEnum
import logging

logger = logging.getLogger(__name__)


class ProcessController(BaseController):
    """
    Enhanced controller for loading, splitting, and processing documents.
    Uses LangChain's document loaders and text splitters with metadata preservation.
    """

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id
        self.project_path = Path(ProjectController().get_project_path(project_id))

    def _get_file_extension(self, file_name: str) -> str:
        """Return file extension including the dot."""
        return Path(file_name).suffix

    def _get_file_loader(self, file_name: str):
        """
        Return the appropriate LangChain document loader for the given file.
        Returns None if the file does not exist or extension is unsupported.
        """
        file_path = os.path.join(
            self.project_path,
            file_name
        )
        if not os.path.exists(file_path):
            return None

        ext = self._get_file_extension(file_name).lower()
        try:
            processing_ext = ProcessingEnum(ext)
        except ValueError:
            return None

        loaders = {
            ProcessingEnum.TXT: TextLoader(str(file_path), encoding="utf-8"),
            ProcessingEnum.PDF: PyMuPDFLoader(str(file_path)),
        }
        return loaders.get(processing_ext)

    def load_documents(self, file_name: str) -> Optional[List[Document]]:
        """
        Load the document(s) from the given file.
        Returns a list of LangChain Document objects, or None if loading fails.
        """
        loader = self._get_file_loader(file_name)
        if loader is None:
            return None
        try:
            return loader.load()
        except Exception as e:
            # Log the error appropriately in production
            logger.error(f"Error loading {file_name}: {e}")
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

    