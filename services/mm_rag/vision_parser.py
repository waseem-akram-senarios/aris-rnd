import base64
import hashlib
import io
import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

import fitz  # PyMuPDF
from PIL import Image

try:
    from openai import OpenAI
except Exception as e:
    OpenAI = None  # type: ignore
    _openai_import_error = e

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class VisionPDFPageParser:
    """
    Render PDF pages -> call OpenAI multimodal model -> extract page text.

    Output per page:
      {
        "page": 1,
        "text": "...",
        "meta": {"source_pdf": "...", "render_dpi": 180, "image_sha256": "..."}
      }

    Caching:
      storage_dir/cache/<image_sha256>.json
    """

    def __init__(
        self,
        storage_dir: str,
        api_key: Optional[str] = None,
        vision_model: Optional[str] = None,
        render_dpi: int = 180,
        max_image_px: int = 2000,
    ) -> None:
        self.api_key = api_key or ARISConfig.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")

        if OpenAI is None:
            raise ImportError(
                f"openai python package is required. Root error: {_openai_import_error}"
            )

        self.client = OpenAI(api_key=self.api_key)
        self.vision_model = vision_model or os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
        self.render_dpi = int(render_dpi)
        self.max_image_px = int(max_image_px)

        self.storage_dir = storage_dir
        self.cache_dir = os.path.join(storage_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def parse_pdf_pages(self, filename: str, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        results: List[Dict[str, Any]] = []

        for idx in range(len(doc)):
            page = doc[idx]
            png = self._render_page_to_png(page)
            img_hash = _sha256_bytes(png)

            cached = self._load_cache(img_hash)
            if cached is not None:
                results.append({
                    "page": idx + 1,
                    "text": cached.get("text", ""),
                    "meta": {
                        "source_pdf": filename,
                        "render_dpi": self.render_dpi,
                        "image_sha256": img_hash,
                        "cached": True,
                    },
                })
                continue

            text = self._extract_text_from_image(png)
            self._save_cache(img_hash, {"text": text})

            results.append({
                "page": idx + 1,
                "text": text,
                "meta": {
                    "source_pdf": filename,
                    "render_dpi": self.render_dpi,
                    "image_sha256": img_hash,
                    "cached": False,
                },
            })

        return results

    def _render_page_to_png(self, page) -> bytes:
        # Render at DPI
        zoom = self.render_dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Downscale if huge (keeps cost + latency sane)
        w, h = img.size
        m = max(w, h)
        if m > self.max_image_px:
            scale = self.max_image_px / float(m)
            img = img.resize((int(w * scale), int(h * scale)))

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def _cache_path(self, img_hash: str) -> str:
        return os.path.join(self.cache_dir, f"{img_hash}.json")

    def _load_cache(self, img_hash: str) -> Optional[Dict[str, Any]]:
        p = self._cache_path(img_hash)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_cache(self, img_hash: str, data: Dict[str, Any]) -> None:
        p = self._cache_path(img_hash)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, p)

    def _extract_text_from_image(self, png_bytes: bytes) -> str:
        """
        Multimodal extraction:
        - Prefer Responses API if available.
        - Fall back to Chat Completions vision format.

        Returns: plain text.
        """
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        data_url = f"data:image/png;base64,{b64}"

        prompt = (
            "You are extracting text from a document page image.\n"
            "Return ONLY the extracted content as plain text.\n"
            "Rules:\n"
            "- Preserve headings and paragraph breaks when obvious.\n"
            "- If there's a table, keep it readable using rows/columns in text.\n"
            "- Do NOT add commentary.\n"
        )

        # Try Responses API
        try:
            resp = self.client.responses.create(
                model=self.vision_model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
            )
            # SDK typically provides output_text
            text = getattr(resp, "output_text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception as e:
            logger.warning(f"Responses API vision extraction failed; fallback to chat.completions. {e}")

        # Fallback: Chat Completions
        try:
            cc = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
            )
            out = cc.choices[0].message.content or ""
            return out.strip()
        except Exception as e:
            raise RuntimeError(f"Vision extraction failed: {type(e).__name__}: {e}")