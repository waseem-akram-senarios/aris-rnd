import hashlib
from typing import List

import numpy as np
from langchain_core.embeddings import Embeddings


def _default_dim_for_model(model_name: str) -> int:
    name = (model_name or "").lower()
    if "3-large" in name:
        return 3072
    return 1536


class LocalHashEmbeddings(Embeddings):
    def __init__(self, model_name: str = "", dim: int | None = None):
        self.model_name = model_name
        self.dim = int(dim or _default_dim_for_model(model_name))

    def _embed_one(self, text: str) -> List[float]:
        data = (text or "").encode("utf-8")
        digest = hashlib.sha256(data).digest()
        seed = int.from_bytes(digest[:8], "big", signed=False)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dim, dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec.astype(np.float32).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_one(text)
