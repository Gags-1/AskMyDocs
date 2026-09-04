import uuid

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore

from .config import (
    QDRANT_URL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION_NAME,
)
from .embeddings import get_embedding_model


def process_pdf(file_path):
    """
    Load a PDF, split it into chunks,
    create embeddings, and store the vectors in Qdrant.

    Returns:
        vector_db: Qdrant vector store
        document_id: Unique ID for this PDF
    """

    # Create a unique ID for this document
    document_id = str(uuid.uuid4())

    # Load the PDF
    loader = PyPDFLoader(file_path=file_path)
    docs = loader.load()

    # Split the PDF into smaller chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    split_docs = text_splitter.split_documents(
        documents=docs
    )

    # Add document ID to every chunk
    for document in split_docs:
        document.metadata["document_id"] = document_id

    # Create embeddings
    embedding_model = get_embedding_model()

    # Store chunks and embeddings in Qdrant
    vector_db = QdrantVectorStore.from_documents(
        documents=split_docs,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION_NAME,
        embedding=embedding_model,
        api_key=QDRANT_API_KEY
    )

    return vector_db, document_id


def search_pdf(vector_db, query, document_id):
    """
    Search only the chunks belonging to the
    specified PDF document.
    """

    return vector_db.similarity_search(
        query=query,
        filter={
            "must": [
                {
                    "key": "metadata.document_id",
                    "match": {
                        "value": document_id
                    }
                }
            ]
        }
    )
