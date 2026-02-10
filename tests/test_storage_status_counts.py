import os
import sys
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock
project_root = Path(__file__).parent.parent
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

_service_path = project_root / "api" / "service.py"
_spec = importlib.util.spec_from_file_location("aris_api_service", _service_path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
ServiceContainer = _mod.ServiceContainer


def test_storage_status_uses_registry_text_index_and_opensearch_counts(monkeypatch):
    # Prevent environment-related surprises
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    service = ServiceContainer(
        vector_store_type="opensearch",
        opensearch_domain="dummy-domain",
        opensearch_index="aris-rag-index",
    )

    # Seed registry with a document that has a per-doc index
    doc_id = "doc-1"
    doc_name = "Manual.pdf"
    service.document_registry.add_document(
        doc_id,
        {
            "document_id": doc_id,
            "document_name": doc_name,
            "chunks_created": 0,
            "image_count": 0,
            "images_detected": True,
            "text_index": "aris-doc-doc-1",
        },
    )

    # Patch the symbols that are imported inside ServiceContainer.get_storage_status
    with patch("langchain_openai.OpenAIEmbeddings") as mock_embeddings_cls, patch(
        "vectorstores.opensearch_store.OpenSearchVectorStore"
    ) as mock_text_store_cls, patch(
        "vectorstores.opensearch_images_store.OpenSearchImagesStore"
    ) as mock_images_store_cls:
        mock_embeddings_cls.return_value = MagicMock()

        mock_text_store = MagicMock()
        mock_text_store.count_documents.return_value = 47
        mock_text_store_cls.return_value = mock_text_store

        mock_images_store = MagicMock()
        mock_images_store.count_images_by_source.return_value = 3
        mock_images_store.get_images_by_source.return_value = [
            {"ocr_text": "a" * 10},
            {"ocr_text": "b" * 5},
            {"ocr_text": ""},
        ]
        mock_images_store_cls.return_value = mock_images_store

        status = service.get_storage_status(doc_id)

    assert status["text_index"] == "aris-doc-doc-1"
    assert status["text_chunks_count"] == 47
    assert status["images_count"] == 3
    assert status["total_ocr_text_length"] == 15
