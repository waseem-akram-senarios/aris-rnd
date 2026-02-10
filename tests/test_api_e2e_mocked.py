import uuid

import pytest
from fastapi.testclient import TestClient
import importlib.util
import types
from pathlib import Path
import sys


class _FakeRAGSystem:
    def __init__(self):
        self.vector_store_type = "opensearch"
        self.opensearch_domain = "dummy"
        self.opensearch_index = "aris-rag-index"
        self.vectorstore = object()
        self.active_sources = None
        self.document_index_map = {}

    def load_vectorstore(self, *_args, **_kwargs):
        return True

    def query_with_rag(self, question: str, k: int = 6, **_kwargs):
        return {
            "answer": f"mock-answer: {question}",
            "sources": ["mock-source"],
            "citations": [
                {
                    "id": 1,
                    "source": "mock-source",
                    "page": 1,
                    "snippet": "mock-snippet",
                    "full_text": "mock-full-text",
                    "source_location": "mock-location",
                    "content_type": "text",
                }
            ],
            "num_chunks_used": 1,
            "response_time": 0.01,
            "context_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
        }

    def query_images(self, question: str, source=None, k: int = 5):
        _ = (question, source, k)
        return []


class _FakeMetricsCollector:
    def __init__(self):
        self.processing_metrics = []


class _FakeProcessingResult:
    def __init__(self, document_name: str):
        self.status = "success"
        self.document_name = document_name
        self.chunks_created = 3
        self.tokens_extracted = 10
        self.parser_used = "mock"
        self.error = None
        self.processing_time = 0.01
        self.extraction_percentage = 1.0
        self.images_detected = False
        self.image_count = 0


class _FakeDocumentProcessor:
    def process_document(self, file_path: str, file_content=None, file_name=None, parser_preference=None, document_id=None, progress_callback=None):
        _ = (file_path, file_content, file_name, parser_preference, document_id, progress_callback)
        return _FakeProcessingResult(file_name or file_path)


class _FakeServiceContainer:
    def __init__(self):
        self.rag_system = _FakeRAGSystem()
        self.document_processor = _FakeDocumentProcessor()
        self.metrics_collector = _FakeMetricsCollector()
        self._docs = {}

    def get_document(self, document_id: str):
        return self._docs.get(document_id)

    def list_documents(self):
        return list(self._docs.values())

    def add_document(self, document_id: str, result: dict):
        self._docs[document_id] = result

    def remove_document(self, document_id: str):
        return self._docs.pop(document_id, None) is not None

    def query_text_only(self, question: str, k: int = 6, document_id=None, use_mmr: bool = True):
        _ = (k, document_id, use_mmr)
        return self.rag_system.query_with_rag(question, k=k)

    def query_images_only(self, question: str, k: int = 5, source=None):
        return []

    def get_storage_status(self, document_id: str):
        doc = self.get_document(document_id) or {}
        return {
            "document_id": document_id,
            "document_name": doc.get("document_name", "unknown"),
            "text_index": doc.get("text_index", "aris-rag-index"),
            "text_chunks_count": int(doc.get("chunks_created", 0) or 0),
            "text_storage_status": "completed" if int(doc.get("chunks_created", 0) or 0) > 0 else "pending",
            "text_last_updated": None,
            "images_index": "aris-rag-images-index",
            "images_count": int(doc.get("image_count", 0) or 0),
            "images_storage_status": "pending",
            "images_last_updated": None,
            "ocr_enabled": False,
            "total_ocr_text_length": 0,
        }


@pytest.fixture()
def client(monkeypatch):
    project_root = Path(__file__).parent.parent
    api_pkg_path = str(project_root / "api")
    sys.modules.pop("api", None)
    api_pkg = types.ModuleType("api")
    api_pkg.__path__ = [api_pkg_path]
    sys.modules["api"] = api_pkg

    main_path = project_root / "api" / "main.py"
    spec = importlib.util.spec_from_file_location("aris_api_main", main_path)
    main = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(main)

    fake_container = _FakeServiceContainer()

    def _fake_create_service_container(*_args, **_kwargs):
        return fake_container

    monkeypatch.setattr(main, "create_service_container", _fake_create_service_container, raising=True)

    with TestClient(main.app) as c:
        yield c


def test_api_mocked_e2e_flow(client):
    r = client.get("/health")
    assert r.status_code == 200

    filename = f"t-{uuid.uuid4().hex}.txt"
    upload = client.post(
        "/documents",
        data={"async_process": "false"},
        files={"file": (filename, b"hello world", "text/plain")},
    )
    assert upload.status_code == 201
    doc = upload.json()
    assert doc["document_id"]

    docs = client.get("/documents")
    assert docs.status_code == 200
    payload = docs.json()
    assert payload["total"] >= 1

    q = client.post("/query/text", json={"question": "hello?", "k": 2, "document_id": doc["document_id"], "use_mmr": True})
    assert q.status_code == 200
    qj = q.json()
    assert qj["answer"]
    assert qj["num_chunks_used"] >= 0

    st = client.get(f"/documents/{doc['document_id']}/storage/status")
    assert st.status_code == 200
    sj = st.json()
    assert sj["document_id"] == doc["document_id"]
    assert sj["text_chunks_count"] >= 0
