import os
import json
from typing import List, Dict, Any, Optional, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from shared.config.settings import ARISConfig


class MMIndexer:
    """
    Build and query a local FAISS index from per-page extracted text.

    Storage layout:
      storage/mm_rag/
        datasets/<dataset_name>/
          pages.jsonl
          faiss_index/
            index.faiss
            index.pkl
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

        self.embeddings = OpenAIEmbeddings(
            model=ARISConfig.EMBEDDING_MODEL,
            api_key=ARISConfig.OPENAI_API_KEY,
        )

    def dataset_dir(self, dataset_name: str) -> str:
        return os.path.join(self.base_dir, "datasets", dataset_name)

    def pages_path(self, dataset_name: str) -> str:
        return os.path.join(self.dataset_dir(dataset_name), "pages.jsonl")

    def faiss_dir(self, dataset_name: str) -> str:
        return os.path.join(self.dataset_dir(dataset_name), "faiss_index")

    def write_pages(self, dataset_name: str, pages: List[Dict[str, Any]]) -> None:
        ddir = self.dataset_dir(dataset_name)
        os.makedirs(ddir, exist_ok=True)

        p = self.pages_path(dataset_name)
        with open(p, "a", encoding="utf-8") as f:
            for rec in pages:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def build_or_update_index(
        self,
        dataset_name: str,
        pages: List[Dict[str, Any]],
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
    ) -> Dict[str, Any]:
        """
        Create/update FAISS from new pages.
        Each chunk retains metadata: source_pdf, page.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(chunk_size),
            chunk_overlap=int(chunk_overlap),
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        texts: List[str] = []
        metas: List[Dict[str, Any]] = []

        for rec in pages:
            text = (rec.get("text") or "").strip()
            if not text:
                continue

            page = rec.get("page")
            meta = rec.get("meta") or {}
            source_pdf = meta.get("source_pdf")

            chunks = splitter.split_text(text)
            for i, ch in enumerate(chunks):
                texts.append(ch)
                metas.append({
                    "source_pdf": source_pdf,
                    "page": page,
                    "chunk_index": i,
                })

        if not texts:
            return {"added_chunks": 0, "index_path": self.faiss_dir(dataset_name)}

        idx_dir = self.faiss_dir(dataset_name)
        os.makedirs(idx_dir, exist_ok=True)

        # Load if exists, else create
        if os.path.exists(os.path.join(idx_dir, "index.faiss")):
            vs = FAISS.load_local(idx_dir, self.embeddings, allow_dangerous_deserialization=True)
            vs.add_texts(texts=texts, metadatas=metas)
        else:
            vs = FAISS.from_texts(texts=texts, embedding=self.embeddings, metadatas=metas)

        vs.save_local(idx_dir)

        return {"added_chunks": len(texts), "index_path": idx_dir}

    def search(self, dataset_name: str, query: str, k: int = 6) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Returns list of (text, metadata) from FAISS similarity search.
        """
        idx_dir = self.faiss_dir(dataset_name)
        if not os.path.exists(os.path.join(idx_dir, "index.faiss")):
            return []

        vs = FAISS.load_local(idx_dir, self.embeddings, allow_dangerous_deserialization=True)
        docs = vs.similarity_search(query, k=int(k))
        out: List[Tuple[str, Dict[str, Any]]] = []
        for d in docs:
            out.append((d.page_content, d.metadata or {}))
        return out