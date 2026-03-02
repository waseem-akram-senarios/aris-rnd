import os
from typing import List, Tuple, Dict, Any, Optional

from services.mm_rag.registry import MMDatasetRegistry, MMDatasetState
from services.mm_rag.vision_parser import VisionPDFPageParser
from services.mm_rag.indexer import MMIndexer
from services.mm_rag.qa import MMQASystem


class MultimodalRAGPipeline:
    """
    Orchestrates:
      PDF bytes -> page images -> vision text -> FAISS index -> QA
    """

    def __init__(self, storage_root: str):
        self.storage_root = storage_root
        os.makedirs(self.storage_root, exist_ok=True)

        self.registry = MMDatasetRegistry(os.path.join(self.storage_root, "registry.json"))
        self.parser = VisionPDFPageParser(storage_dir=self.storage_root)
        self.indexer = MMIndexer(base_dir=self.storage_root)
        self.qa = MMQASystem(base_dir=self.storage_root)

    def ensure_dataset(self, dataset_name: str) -> None:
        dataset_name = dataset_name.strip() or "default"
        now = self.registry.now_ts()
        existing = self.registry.get(dataset_name)
        if existing:
            existing.updated_at = now
            self.registry.upsert(existing)
            return
        self.registry.upsert(MMDatasetState(dataset_name=dataset_name, created_at=now, updated_at=now))

    def ingest_files(self, dataset_name: str, uploaded_files: List[Tuple[str, bytes]]) -> Dict[str, Any]:
        self.ensure_dataset(dataset_name)

        all_pages: List[Dict[str, Any]] = []
        for filename, content in uploaded_files:
            if filename.lower().endswith(".pdf"):
                pages = self.parser.parse_pdf_pages(filename, content)
                all_pages.extend(pages)
            else:
                # Non-PDF: store as a single "page" record
                all_pages.append({
                    "page": 1,
                    "text": content.decode("utf-8", errors="ignore"),
                    "meta": {"source_pdf": filename, "render_dpi": None, "image_sha256": None, "cached": False},
                })

        # Persist raw page extraction
        self.indexer.write_pages(dataset_name, all_pages)

        # Index (chunked, but metadata retains page)
        idx_res = self.indexer.build_or_update_index(dataset_name, all_pages)

        return {
            "dataset": dataset_name,
            "pages_processed": len(all_pages),
            "index": idx_res,
        }

    def ask(self, dataset_name: str, question: str, k: int = 6) -> Dict[str, Any]:
        ans = self.qa.answer(dataset_name, question, k=k)
        return {"answer": ans.answer, "citations": ans.citations}