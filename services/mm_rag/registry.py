import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class MMDatasetState:
    dataset_name: str
    created_at: int
    updated_at: int


class MMDatasetRegistry:
    """
    Local registry for multimodal datasets (for Streamlit convenience).
    """
    def __init__(self, path: str):
        self.path = path
        self._state: Dict[str, Any] = {"version": 1, "datasets": {}}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._state = json.load(f)
        except Exception:
            self._state = {"version": 1, "datasets": {}}
        if "datasets" not in self._state:
            self._state["datasets"] = {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def list(self) -> Dict[str, MMDatasetState]:
        out: Dict[str, MMDatasetState] = {}
        for name, raw in (self._state.get("datasets") or {}).items():
            try:
                out[name] = MMDatasetState(**raw)
            except Exception:
                continue
        return out

    def get(self, dataset_name: str) -> Optional[MMDatasetState]:
        raw = (self._state.get("datasets") or {}).get(dataset_name)
        if not raw:
            return None
        try:
            return MMDatasetState(**raw)
        except Exception:
            return None

    def upsert(self, ds: MMDatasetState) -> None:
        self._state.setdefault("datasets", {})
        self._state["datasets"][ds.dataset_name] = asdict(ds)
        self.save()

    def delete(self, dataset_name: str) -> None:
        if dataset_name in (self._state.get("datasets") or {}):
            del self._state["datasets"][dataset_name]
            self.save()

    @staticmethod
    def now_ts() -> int:
        return int(time.time())