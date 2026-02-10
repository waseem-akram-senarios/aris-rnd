import base64
import os
import tempfile
import time
from typing import Optional, Dict, Any

import requests
from requests import exceptions as requests_exceptions

from .base_parser import BaseParser, ParsedDocument
from scripts.setup_logging import get_logger

logger = get_logger("aris_rag.llama_scan_parser")


class LlamaScanParser(BaseParser):
    def __init__(
        self,
        model: Optional[str] = None,
        server_url: Optional[str] = None,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
        width: Optional[int] = None,
        include_diagrams: Optional[bool] = None,
        custom_instructions: Optional[str] = None,
    ):
        super().__init__("llamascan")

        # Default to llava if available, fallback to qwen2.5vl
        self.model = model or os.getenv("LLAMA_SCAN_MODEL", "llava:latest")
        self.server_url = (server_url or os.getenv("OLLAMA_SERVER_URL", "http://localhost:11434")).rstrip("/")

        self.start_page = int(start_page) if start_page is not None else int(os.getenv("LLAMA_SCAN_START_PAGE", "0"))
        self.end_page = int(end_page) if end_page is not None else int(os.getenv("LLAMA_SCAN_END_PAGE", "0"))
        self.width = int(width) if width is not None else int(os.getenv("LLAMA_SCAN_WIDTH", "0"))

        self.ollama_timeout_seconds = int(
            os.getenv("LLAMA_SCAN_OLLAMA_TIMEOUT_SECONDS", os.getenv("OLLAMA_TIMEOUT_SECONDS", "600"))
        )
        self.ollama_retries = int(os.getenv("LLAMA_SCAN_OLLAMA_RETRIES", "1"))

        if include_diagrams is None:
            include_diagrams_env = os.getenv("LLAMA_SCAN_INCLUDE_DIAGRAMS", "true").strip().lower()
            include_diagrams = include_diagrams_env in {"1", "true", "yes", "y", "on"}
        self.include_diagrams = bool(include_diagrams)

        self.custom_instructions = custom_instructions or os.getenv("LLAMA_SCAN_CUSTOM_INSTRUCTIONS", "").strip() or None

        self._check_dependencies()

    @staticmethod
    def _check_dependencies() -> None:
        try:
            import fitz  # noqa: F401
        except Exception as e:
            raise ImportError("PyMuPDF (pymupdf) is required for LlamaScanParser") from e

        try:
            import llama_scan  # noqa: F401
        except Exception:
            logger.warning("llama-scan is not installed or dependencies missing. Install with: pip install llama-scan")

    def _check_ollama_server(self) -> bool:
        """Checks if Ollama server is reachable and model is available."""
        # Step 1: Check connectivity
        urls_to_try = [self.server_url]
        
        # If localhost fails and we're likely in Docker, try host.docker.internal as fallback
        if "localhost" in self.server_url or "127.0.0.1" in self.server_url:
            urls_to_try.append(self.server_url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal"))

        for url in urls_to_try:
            try:
                resp = requests.get(f"{url}/api/tags", timeout=3)
                if resp.status_code == 200:
                    # Connection successful, now check if the specific model exists
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    
                    # Exact match or base name match (e.g., qwen2.5vl matches qwen2.5vl:latest)
                    model_match = any(self.model in m or m in self.model for m in models)
                    
                    if not model_match:
                        logger.warning(f"Llama-Scan: Ollama reachable at {url}, but model '{self.model}' not found in {models}")
                        return False
                    
                    if url != self.server_url:
                        logger.info(f"Llama-Scan: Successfully connected to Ollama via fallback URL: {url}")
                        self.server_url = url # Update for future calls
                    return True
            except Exception as e:
                logger.debug(f"Llama-Scan: Connection attempt to {url} failed: {e}")
                continue
        
        logger.warning(f"Llama-Scan: Could not connect to Ollama server at any of {urls_to_try}")
        return False

    def is_available(self) -> bool:
        return self._check_ollama_server()

    def can_parse(self, file_path: str) -> bool:
        return file_path.lower().endswith(".pdf") and self.is_available()

    def _build_prompt(self) -> str:
        # OPTIMIZED FOR MAXIMUM ACCURACY
        prompt = (
            "Task: Perform highly accurate text extraction from this PDF page image.\n\n"
            "CRITICAL ACCURACY REQUIREMENTS:\n"
            "1. Transcribe ALL text exactly as it appears - every word, number, and symbol.\n"
            "2. Preserve the EXACT formatting: headings, bold, italics, lists, tables, columns.\n"
            "3. Maintain reading order: left-to-right, top-to-bottom for each column/section.\n"
            "4. Include ALL text from headers, footers, sidebars, and captions.\n"
            "5. For tables: preserve structure using Markdown table syntax.\n"
            "6. For multi-column layouts: transcribe each column separately.\n"
            "7. Include special characters, symbols, and mathematical notation.\n"
            "8. Do NOT summarize, paraphrase, or skip any content.\n"
            "9. Do NOT include page numbers.\n\n"
        )

        if self.include_diagrams:
            prompt += (
                "IMAGE/DIAGRAM HANDLING:\n"
                "- For EACH image or diagram, provide a DETAILED description.\n"
                "- Describe: what it shows, any text/labels, relationships, and meaning.\n"
                "- Include any data values, measurements, or annotations visible.\n"
                "- Enclose the description in an <image> tag.\n"
                "- Example: <image>Flow chart showing 4 steps: Input → Process → Validation → Output</image>\n\n"
            )
        else:
            prompt += "- Focus only on textual content, ignore images/diagrams.\n\n"

        if self.custom_instructions:
            prompt += f"ADDITIONAL REQUIREMENTS:\n{self.custom_instructions}\n\n"

        prompt += "Begin transcription now:"
        return prompt

    def _ollama_generate(self, image_png_bytes: bytes, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "images": [base64.b64encode(image_png_bytes).decode("utf-8")],
        }

        last_err: Optional[Exception] = None
        attempts = max(1, self.ollama_retries + 1)
        for attempt in range(1, attempts + 1):
            try:
                resp = requests.post(
                    f"{self.server_url}/api/generate",
                    json=payload,
                    timeout=self.ollama_timeout_seconds,
                )
                if resp.status_code != 200:
                    raise ValueError(f"Ollama generate failed ({resp.status_code}): {resp.text[:300]}")

                data = resp.json() or {}
                return data.get("response", "") or ""
            except (
                requests_exceptions.ReadTimeout,
                requests_exceptions.Timeout,
                requests_exceptions.ConnectionError,
                requests_exceptions.ChunkedEncodingError,
            ) as e:
                last_err = e
                if attempt < attempts:
                    time.sleep(min(5, attempt))
                    continue
                raise
            except Exception as e:
                last_err = e
                raise

        raise last_err or RuntimeError("Ollama generate failed")

    def parse(
        self,
        file_path: str,
        file_content: Optional[bytes] = None,
        progress_callback: Optional[callable] = None,
    ) -> ParsedDocument:
        if not self.is_available():
            raise ValueError(
                "Llama-Scan requires an Ollama server with a vision model. "
                "Set OLLAMA_SERVER_URL and ensure Ollama is running."
            )

        import fitz

        if progress_callback:
            progress_callback("parsing", 0.0, detailed_message="Initializing Llama-Scan (Ollama multimodal)...")

        input_path = file_path
        temp_dir = None
        try:
            if file_content is not None:
                temp_dir = tempfile.TemporaryDirectory()
                input_path = os.path.join(temp_dir.name, "input.pdf")
                with open(input_path, "wb") as f:
                    f.write(file_content)

            doc = fitz.open(input_path)
            total_pages = len(doc)

            start = 1 if self.start_page == 0 else self.start_page
            end = total_pages if self.end_page == 0 else self.end_page

            if start < 1 or start > total_pages:
                raise ValueError(f"Start page {start} out of range (doc has {total_pages} pages)")
            if end < 1 or end > total_pages:
                raise ValueError(f"End page {end} out of range (doc has {total_pages} pages)")
            if end < start:
                raise ValueError(f"End page {end} must be >= start page {start}")

            pages_to_process = list(range(start, end + 1))
            prompt = self._build_prompt()

            text_parts = []
            page_blocks = []
            cumulative_pos = 0
            pages_with_text = 0

            for idx, page_num in enumerate(pages_to_process, 1):
                page = doc[page_num - 1]

                if progress_callback:
                    progress_callback(
                        "parsing",
                        0.05 + 0.90 * (idx / max(1, len(pages_to_process))),
                        detailed_message=f"Llama-Scan: Transcribing page {page_num}/{total_pages}...",
                    )

                # OPTIMIZED FOR MAXIMUM ACCURACY - Higher resolution for better OCR
                # Default to 2x zoom for better text recognition (if width not specified)
                default_zoom = 2.0  # 2x resolution for better accuracy
                matrix = fitz.Matrix(default_zoom, default_zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)  # No alpha channel for cleaner image
                
                # If specific width requested, recalculate zoom
                if self.width and pix.width and self.width > 0 and pix.width != self.width:
                    zoom = self.width / float(pix.width) * default_zoom
                    matrix = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)

                page_text = self._ollama_generate(pix.tobytes("png"), prompt).strip()
                if page_text:
                    pages_with_text += 1

                page_text_with_marker = f"--- Page {page_num} ---\n{page_text}".strip()
                page_start = cumulative_pos
                page_end = page_start + len(page_text_with_marker)

                text_parts.append(page_text_with_marker)
                page_blocks.append(
                    {
                        "type": "page",
                        "page": page_num,
                        "text": page_text,
                        "start_char": page_start,
                        "end_char": page_end,
                    }
                )
                cumulative_pos = page_end + 2

            doc.close()

            full_text = "\n\n".join(text_parts)
            extraction_percentage = (pages_with_text / max(1, len(pages_to_process))) if pages_to_process else 0.0

            if progress_callback:
                progress_callback("parsing", 1.0, detailed_message="Llama-Scan parsing complete")

            # Extract images from page_blocks for OpenSearch storage
            extracted_images = []
            if self.include_diagrams:
                # Look for <image> tags in the text
                import re
                for page_block in page_blocks:
                    page_num = page_block.get('page', 1)
                    page_text = page_block.get('text', '')
                    
                    # Find all <image> tags and their content
                    image_matches = re.findall(r'<image>(.*?)</image>', page_text, re.DOTALL)
                    for img_idx, img_content in enumerate(image_matches, 1):
                        extracted_images.append({
                            'source': os.path.basename(file_path),
                            'image_number': len(extracted_images) + 1,
                            'page': page_num,
                            'ocr_text': img_content.strip(),
                            'ocr_text_length': len(img_content.strip()),
                            'marker_detected': True,
                            'extraction_method': 'llamascan_ocr',
                        })
            
            return ParsedDocument(
                text=full_text,
                metadata={
                    "source": os.path.basename(file_path),
                    "parser": "llamascan",
                    "page_blocks": page_blocks,
                    "pages": total_pages,
                    "llama_scan_model": self.model,
                    "ollama_server_url": self.server_url,
                    "llama_scan_start_page": start,
                    "llama_scan_end_page": end,
                    "include_diagrams": self.include_diagrams,
                    "extracted_images": extracted_images,  # Add extracted images for OpenSearch
                },
                pages=total_pages,
                images_detected=self.include_diagrams and len(extracted_images) > 0,
                parser_used="llamascan",
                confidence=0.9,
                extraction_percentage=float(extraction_percentage),
                image_count=len(extracted_images),
            )

        finally:
            if temp_dir is not None:
                temp_dir.cleanup()
