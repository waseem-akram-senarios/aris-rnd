import os
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

try:
    from openai import OpenAI
except Exception as e:
    OpenAI = None  # type: ignore
    _openai_import_error = e

from shared.config.settings import ARISConfig
from services.mm_rag.indexer import MMIndexer


@dataclass
class MMCitation:
    source_pdf: Optional[str]
    page: Optional[int]
    chunk_index: Optional[int]


@dataclass
class MMAnswer:
    answer: str
    citations: List[Dict[str, Any]]


class MMQASystem:
    """
    Retrieval from local FAISS + answering via OpenAI text model.
    Citations are deterministic: (source_pdf, page) come from metadata.
    """

    def __init__(self, base_dir: str, model: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or ARISConfig.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

        if OpenAI is None:
            raise ImportError(f"openai is required. Root error: {_openai_import_error}")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model or ARISConfig.OPENAI_MODEL or "gpt-4o"
        self.indexer = MMIndexer(base_dir=base_dir)

    def answer(self, dataset_name: str, question: str, k: int = 6) -> MMAnswer:
        hits = self.indexer.search(dataset_name, question, k=k)

        # Build context with explicit page anchors
        context_blocks: List[str] = []
        citations: List[Dict[str, Any]] = []

        seen = set()
        for text, meta in hits:
            src = meta.get("source_pdf")
            page = meta.get("page")
            chunk_index = meta.get("chunk_index")

            key = (src, page, chunk_index)
            if key in seen:
                continue
            seen.add(key)

            tag = f"[source={src} page={page} chunk={chunk_index}]"
            context_blocks.append(f"{tag}\n{text}")

            citations.append({
                "source_pdf": src,
                "page": page,
                "chunk_index": chunk_index,
            })

        context = "\n\n---\n\n".join(context_blocks).strip()

        sys_prompt = (
            "You are a document QA system.\n"
            "Answer ONLY using the provided context.\n"
            "If the answer is missing, say you cannot find it in the documents.\n"
            "When you use a fact, cite it with (source=<file> page=<n>).\n"
        )

        user_prompt = (
            f"Question:\n{question}\n\n"
            f"Context:\n{context if context else '[NO CONTEXT FOUND]'}\n\n"
            "Return:\n"
            "1) Answer text.\n"
            "2) Include citations inline like: (source=... page=...).\n"
        )

        if not context:
            return MMAnswer(
                answer="I cannot find relevant information in the indexed documents for this question.",
                citations=[],
            )

        # Try Responses API first; fall back to chat.completions if needed
        answer_text = None
        try:
            resp = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": sys_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                ],
            )
            answer_text = getattr(resp, "output_text", None)
        except Exception:
            answer_text = None

        if not isinstance(answer_text, str) or not answer_text.strip():
            cc = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            answer_text = cc.choices[0].message.content or ""

        return MMAnswer(answer=answer_text.strip(), citations=citations)