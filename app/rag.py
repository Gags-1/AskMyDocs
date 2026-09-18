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


def extract_pdf(file_path):
    """
    Extract pages from a PDF.

    Returns:
        list[Document]: One LangChain Document per PDF page.
    """

    loader = PyPDFLoader(file_path=file_path)

    docs = loader.load()

    if not docs:
        raise ValueError(
            "No pages could be extracted from the PDF."
        )

    return docs


def find_pages_needing_ocr(docs):
    """
    Identify PDF pages where text extraction
    produced no usable text.

    Returns:
        list[int]: Zero-based page numbers requiring OCR.
    """

    pages_needing_ocr = []

    for doc in docs:

        text = doc.page_content.strip()

        if not text:

            page_number = doc.metadata.get(
                "page"
            )

            pages_needing_ocr.append(
                page_number
            )

    return pages_needing_ocr


def validate_extraction(docs):
    """
    Perform basic extraction quality checks.
    """

    if not docs:
        raise ValueError(
            "PDF extraction returned no pages."
        )

    pages_needing_ocr = find_pages_needing_ocr(
        docs
    )

    pages_with_text = (
        len(docs) - len(pages_needing_ocr)
    )

    extraction_coverage = (
        pages_with_text / len(docs)
    )

    return {
        "total_pages": len(docs),
        "pages_with_text": pages_with_text,
        "pages_needing_ocr": pages_needing_ocr,
        "extraction_coverage": extraction_coverage,
    }


def chunk_documents(docs):
    """
    Split extracted documents into smaller chunks.
    """

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    return text_splitter.split_documents(
        documents=docs
    )


def process_pdf(file_path):
    """
    Process a PDF through the RAG ingestion pipeline.

    PDF
      ↓
    extraction
      ↓
    validation
      ↓
    chunking
      ↓
    embeddings
      ↓
    Qdrant
    """

    document_id = str(
        uuid.uuid4()
    )

    # -------------------------------
    # 1. Extract
    # -------------------------------

    docs = extract_pdf(
        file_path
    )

    # -------------------------------
    # 2. Validate extraction
    # -------------------------------

    extraction_report = validate_extraction(
        docs
    )

    print(
        "Extraction report:",
        extraction_report
    )

    # -------------------------------
    # 3. Chunk
    # -------------------------------

    split_docs = chunk_documents(
        docs
    )

    # -------------------------------
    # 4. Add document ID
    # -------------------------------

    for document in split_docs:

        document.metadata[
            "document_id"
        ] = document_id

    # -------------------------------
    # 5. Create embeddings
    # -------------------------------

    embedding_model = (
        get_embedding_model()
    )

    # -------------------------------
    # 6. Store in Qdrant
    # -------------------------------

    vector_db = (
        QdrantVectorStore.from_documents(
            documents=split_docs,
            url=QDRANT_URL,
            collection_name=QDRANT_COLLECTION_NAME,
            embedding=embedding_model,
            api_key=QDRANT_API_KEY
        )
    )

    return (
        vector_db,
        document_id
    )


def search_pdf(
    vector_db,
    query,
    document_id
):
    """
    Search only chunks belonging
    to the specified PDF.
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
