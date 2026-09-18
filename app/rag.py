import io
import uuid

import pymupdf
import pytesseract

from PIL import Image
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
    loader = PyPDFLoader(file_path=file_path)
    docs = loader.load()

    if not docs:
        raise ValueError("No pages could be extracted from the PDF.")

    return docs


def classify_pages(docs):
    """
    Classify pages based on the initial text extraction.

    TEXT  -> page contains usable extracted text
    BLANK -> page contains no text and appears to be blank
    OCR   -> page has no extractable text and may be scanned
    """

    classifications = []

    for doc in docs:
        page_number = doc.metadata.get("page")
        text = doc.page_content.strip()

        if text:
            page_type = "TEXT"
        else:
            page_type = "OCR"

        classifications.append(
            {
                "page": page_number,
                "type": page_type,
            }
        )

    return classifications


def find_pages_needing_ocr(docs):
    pages_needing_ocr = []

    for doc in docs:
        text = doc.page_content.strip()

        if not text:
            page_number = doc.metadata.get("page")
            pages_needing_ocr.append(page_number)

    return pages_needing_ocr


def validate_extraction(docs):
    if not docs:
        raise ValueError("PDF extraction returned no pages.")

    pages_needing_ocr = find_pages_needing_ocr(docs)
    pages_with_text = len(docs) - len(pages_needing_ocr)

    extraction_coverage = pages_with_text / len(docs)

    return {
        "total_pages": len(docs),
        "pages_with_text": pages_with_text,
        "pages_needing_ocr": pages_needing_ocr,
        "extraction_coverage": extraction_coverage,
    }


def ocr_pages(file_path, pages):
    pdf = pymupdf.open(file_path)
    ocr_docs = []

    try:
        for page_number in pages:
            page = pdf[page_number]

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(2, 2)
            )

            image = Image.open(
                io.BytesIO(
                    pixmap.tobytes("png")
                )
            )

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


def validate_ocr_quality(text):
    text = text.strip()

    if not text:
        return {
            "valid": False,
            "reason": "empty_text",
            "character_count": 0,
            "alphabetic_ratio": 0,
        }

    character_count = len(text)

    alphabetic_characters = sum(
        character.isalpha()
        for character in text
    )

    alphabetic_ratio = (
        alphabetic_characters / character_count
        if character_count > 0
        else 0
    )

    if character_count < 20:
        return {
            "valid": False,
            "reason": "too_little_text",
            "character_count": character_count,
            "alphabetic_ratio": alphabetic_ratio,
        }

    if alphabetic_ratio < 0.20:
        return {
            "valid": False,
            "reason": "low_alphabetic_ratio",
            "character_count": character_count,
            "alphabetic_ratio": alphabetic_ratio,
        }

    return {
        "valid": True,
        "reason": "acceptable",
        "character_count": character_count,
        "alphabetic_ratio": alphabetic_ratio,
    }


def validate_ocr_documents(ocr_docs):
    failed_pages = []
    quality_reports = []

    for doc in ocr_docs:
        page_number = doc.metadata.get("page")

        quality = validate_ocr_quality(
            doc.page_content
        )

        quality_reports.append(
            {
                "page": page_number,
                **quality,
            }
        )

        if not quality["valid"]:
            failed_pages.append(page_number)

    return {
        "total_ocr_pages": len(ocr_docs),
        "failed_pages": failed_pages,
        "quality_reports": quality_reports,
    }


def normalize_metadata(docs, document_id):
    for document in docs:
        page_number = document.metadata.get("page")

        if page_number is not None:
            document.metadata["page_label"] = (
                page_number + 1
            )

        document.metadata["document_id"] = document_id

        if "extraction_method" not in document.metadata:
            document.metadata["extraction_method"] = "text"

    return docs


def chunk_documents(docs):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    return text_splitter.split_documents(
        documents=docs
    )


def process_pdf(file_path):
    document_id = str(uuid.uuid4())

    # 1. Extract
    docs = extract_pdf(file_path)

    # 2. Classify
    page_classifications = classify_pages(docs)

    print(
        "Page classifications:",
        page_classifications
    )

    # 3. Validate extraction
    extraction_report = validate_extraction(docs)

    print(
        "Extraction report:",
        extraction_report
    )

    pages_needing_ocr = (
        extraction_report["pages_needing_ocr"]
    )

    # 4. OCR fallback
    if pages_needing_ocr:

        print(
            "Running OCR on pages:",
            pages_needing_ocr
        )

        ocr_docs = ocr_pages(
            file_path,
            pages_needing_ocr
        )

        # 5. Validate OCR
        ocr_report = validate_ocr_documents(
            ocr_docs
        )

        print(
            "OCR quality report:",
            ocr_report
        )

        # 6. Replace failed extraction
        docs_by_page = {
            doc.metadata.get("page"): doc
            for doc in docs
        }

        for ocr_doc in ocr_docs:

            page_number = ocr_doc.metadata["page"]

            docs_by_page[page_number] = ocr_doc

        docs = [
            docs_by_page[page_number]
            for page_number in sorted(docs_by_page)
        ]

    # 7. Normalize metadata
    docs = normalize_metadata(
        docs,
        document_id
    )

    # 8. Chunk
    split_docs = chunk_documents(docs)

    # 9. Embeddings
    embedding_model = get_embedding_model()

    # 10. Qdrant
    vector_db = QdrantVectorStore.from_documents(
        documents=split_docs,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION_NAME,
        embedding=embedding_model,
        api_key=QDRANT_API_KEY,
    )

    return vector_db, document_id


def search_pdf(vector_db, query, document_id):
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
