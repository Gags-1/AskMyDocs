import io
import uuid
from PIL import Image
import fitz
import pytesseract

from langchain_core.documents import Document
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
    Extract pages from a PDF using PyPDFLoader.
    """

    loader = PyPDFLoader(
        file_path=file_path
    )

    docs = loader.load()

    if not docs:
        raise ValueError(
            "No pages could be extracted from the PDF."
        )

    return docs


def find_pages_needing_ocr(docs):
    """
    Identify pages where normal PDF text extraction
    produced no usable text.
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
    Calculate basic PDF extraction quality.
    """

    if not docs:
        raise ValueError(
            "PDF extraction returned no pages."
        )

    pages_needing_ocr = (
        find_pages_needing_ocr(docs)
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


def ocr_pages(file_path, pages):
    """
    Run OCR on selected PDF pages.
    """

    pdf = fitz.open(
        file_path
    )

    ocr_docs = []

    try:

        for page_number in pages:

            page = pdf[page_number]

            # Render PDF page as an image.
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(2, 2)
            )

            # Convert image bytes into a PIL image.
            image = Image.open(
                io.BytesIO(
                    pixmap.tobytes("png")
                )
            )

            # Run OCR.
            text = pytesseract.image_to_string(
                image
            ).strip()

            if text:

                ocr_docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": file_path,
                            "page": page_number,
                            "page_label": page_number + 1,
                            "extraction_method": "ocr",
                        },
                    )
                )

    finally:

        pdf.close()

    return ocr_docs


def normalize_metadata(
    docs,
    document_id
):
    """
    Ensure every document follows the same
    metadata schema regardless of extraction method.
    """

    for document in docs:

        page_number = document.metadata.get(
            "page"
        )

        if page_number is not None:

            document.metadata[
                "page_label"
            ] = page_number + 1

        document.metadata[
            "document_id"
        ] = document_id

        if "extraction_method" not in document.metadata:

            document.metadata[
                "extraction_method"
            ] = "text"

    return docs


def chunk_documents(docs):
    """
    Split documents into smaller overlapping chunks.
    """

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
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
    OCR fallback
      ↓
    metadata normalization
      ↓
    chunking
      ↓
    embeddings
      ↓
    Qdrant
    """

    # --------------------------------
    # 1. Generate document ID
    # --------------------------------

    document_id = str(
        uuid.uuid4()
    )

    # --------------------------------
    # 2. Extract PDF
    # --------------------------------

    docs = extract_pdf(
        file_path
    )

    # --------------------------------
    # 3. Validate extraction
    # --------------------------------

    extraction_report = validate_extraction(
        docs
    )

    print(
        "Extraction report:",
        extraction_report
    )

    # --------------------------------
    # 4. OCR fallback
    # --------------------------------

    pages_needing_ocr = (
        extraction_report[
            "pages_needing_ocr"
        ]
    )

    if pages_needing_ocr:

        print(
            "Running OCR on pages:",
            pages_needing_ocr
        )

        ocr_docs = ocr_pages(
            file_path,
            pages_needing_ocr
        )

        # Map documents by page.
        docs_by_page = {
            doc.metadata.get("page"): doc
            for doc in docs
        }

        # Replace pages with OCR results.
        for ocr_doc in ocr_docs:

            page_number = (
                ocr_doc.metadata[
                    "page"
                ]
            )

            docs_by_page[
                page_number
            ] = ocr_doc

        # Restore page order.
        docs = [
            docs_by_page[page_number]
            for page_number in sorted(
                docs_by_page
            )
        ]

    # --------------------------------
    # 5. Normalize metadata
    # --------------------------------

    docs = normalize_metadata(
        docs,
        document_id
    )

    # --------------------------------
    # 6. Chunk
    # --------------------------------

    split_docs = chunk_documents(
        docs
    )

    # --------------------------------
    # 7. Create embeddings
    # --------------------------------

    embedding_model = (
        get_embedding_model()
    )

    # --------------------------------
    # 8. Store in Qdrant
    # --------------------------------

    vector_db = (
        QdrantVectorStore.from_documents(
            documents=split_docs,
            url=QDRANT_URL,
            collection_name=QDRANT_COLLECTION_NAME,
            embedding=embedding_model,
            api_key=QDRANT_API_KEY,
        )
    )

    return (
        vector_db,
        document_id,
    )


def search_pdf(
    vector_db,
    query,
    document_id,
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
                    },
                }
            ]
        },
    )
