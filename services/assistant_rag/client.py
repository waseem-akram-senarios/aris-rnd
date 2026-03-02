import io
import os
import time
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

try:
    from openai import OpenAI
except Exception as e:
    OpenAI = None  # type: ignore
    _openai_import_error = e

from shared.config.settings import ARISConfig
from services.assistant_rag.registry import AssistantRegistry, DatasetState

logger = logging.getLogger(__name__)


@dataclass
class AssistantAnswer:
    text: str
    citations: List[Dict[str, Any]]
    raw_message_id: Optional[str] = None
    raw_thread_id: Optional[str] = None
    raw_run_id: Optional[str] = None


class AssistantRAGClient:
    """
    RAG via OpenAI Assistants API (file_search + vector stores).

    Key design choice:
    - Assistants API supports ONE vector store per assistant, so we use ONE assistant per "dataset".
    """

    def __init__(
        self,
        registry_path: str,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        assistant_name_prefix: str = "ARIS-Assistant-RAG",
    ) -> None:
        self.api_key = api_key or ARISConfig.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set. Set it in .env or environment.")

        if OpenAI is None:
            raise ImportError(
                f"openai python package is required for Assistant mode. "
                f"Install 'openai' and retry. Root error: {_openai_import_error}"
            )

        self.client = OpenAI(api_key=self.api_key)
        self.default_model = default_model or ARISConfig.OPENAI_MODEL or "gpt-4o"
        self.assistant_name_prefix = assistant_name_prefix
        self.registry = AssistantRegistry(registry_path)

    # ----------------------------
    # Dataset lifecycle
    # ----------------------------

    def ensure_dataset(self, dataset_name: str, model: Optional[str] = None) -> DatasetState:
        """
        Ensure an Assistant + Vector Store exist for the dataset.
        If registry contains IDs, validate they still exist (best-effort) or recreate.
        """
        dataset_name = dataset_name.strip()
        if not dataset_name:
            raise ValueError("dataset_name cannot be empty")

        desired_model = model or self.default_model
        existing = self.registry.get(dataset_name)
        now = self.registry.now_ts()

        if existing:
            # Best-effort validation
            try:
                _ = self.client.beta.assistants.retrieve(existing.assistant_id)
                _ = self.client.vector_stores.retrieve(existing.vector_store_id)

                # If model changed, update assistant model for future runs
                if existing.model != desired_model:
                    self.client.beta.assistants.update(
                        assistant_id=existing.assistant_id,
                        model=desired_model,
                    )
                    existing.model = desired_model
                    existing.updated_at = now
                    self.registry.upsert(existing)

                return existing
            except Exception as e:
                logger.warning(
                    f"Dataset '{dataset_name}' registry stale; recreating. "
                    f"Reason: {type(e).__name__}: {e}"
                )

        # Create fresh assistant + vector store
        assistant = self.client.beta.assistants.create(
            name=f"{self.assistant_name_prefix}:{dataset_name}",
            model=desired_model,
            instructions=self._default_instructions(),
            tools=[{"type": "file_search"}],
        )
        vector_store = self.client.vector_stores.create(name=f"ARIS:{dataset_name}")

        # Attach vector store to assistant
        self.client.beta.assistants.update(
            assistant_id=assistant.id,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )

        state = DatasetState(
            dataset_name=dataset_name,
            assistant_id=assistant.id,
            vector_store_id=vector_store.id,
            model=desired_model,
            created_at=now,
            updated_at=now,
        )
        self.registry.upsert(state)
        return state

    def delete_dataset_local(self, dataset_name: str) -> None:
        """
        Deletes registry entry only (does NOT delete OpenAI objects).
        Useful if IDs got stale; you can recreate with ensure_dataset.
        """
        self.registry.delete(dataset_name)

    # ----------------------------
    # Ingestion
    # ----------------------------

    def upload_files_to_dataset(
        self,
        dataset_name: str,
        uploaded_files: List[Tuple[str, bytes]],
        model: Optional[str] = None,
        poll_timeout_s: int = 600,
    ) -> Dict[str, Any]:
        """
        Upload files into the dataset's vector store.

        Args:
            uploaded_files: list of (filename, bytes)
        Returns:
            {"vector_store_id": "...", "file_batch_status": "...", "file_counts": {...}}
        """
        state = self.ensure_dataset(dataset_name, model=model)

        file_streams = []
        for filename, content in uploaded_files:
            bio = io.BytesIO(content)
            bio.name = filename  # used by SDK helper
            file_streams.append(bio)

        # Preferred: SDK helper upload_and_poll
        try:
            file_batch = self.client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=state.vector_store_id,
                files=file_streams,
            )
            return {
                "vector_store_id": state.vector_store_id,
                "file_batch_status": getattr(file_batch, "status", None),
                "file_counts": getattr(file_batch, "file_counts", None),
            }
        except Exception as e:
            logger.warning(
                f"upload_and_poll helper failed; falling back to manual upload. "
                f"{type(e).__name__}: {e}"
            )

        # Fallback: manual upload + attach + poll
        file_ids = []
        for stream in file_streams:
            stream.seek(0)
            fobj = self.client.files.create(file=stream, purpose="assistants")
            file_ids.append(fobj.id)

        for fid in file_ids:
            _ = self.client.vector_stores.files.create(
                vector_store_id=state.vector_store_id,
                file_id=fid,
            )

        self._poll_vector_store_ready(state.vector_store_id, timeout_s=poll_timeout_s)

        return {
            "vector_store_id": state.vector_store_id,
            "file_batch_status": "completed",
            "file_counts": {
                "completed": len(file_ids),
                "failed": 0,
                "in_progress": 0,
                "total": len(file_ids),
            },
        }

    def _poll_vector_store_ready(self, vector_store_id: str, timeout_s: int = 600) -> None:
        start = time.time()
        while True:
            vs = self.client.vector_stores.retrieve(vector_store_id)
            status = getattr(vs, "status", None)
            if status == "completed":
                return
            if time.time() - start > timeout_s:
                raise TimeoutError(
                    f"Vector store did not reach 'completed' within {timeout_s}s (status={status})"
                )
            time.sleep(2)

    # ----------------------------
    # Retrieval (Q&A)
    # ----------------------------

    def ask(
        self,
        dataset_name: str,
        question: str,
        model: Optional[str] = None,
        force_file_search: bool = True,
    ) -> AssistantAnswer:
        """
        Ask a question against the dataset via Assistants file_search.
        """
        state = self.ensure_dataset(dataset_name, model=model)

        thread = self.client.beta.threads.create(
            messages=[{"role": "user", "content": question}]
        )

        run_kwargs: Dict[str, Any] = {"thread_id": thread.id, "assistant_id": state.assistant_id}

        # Best-effort forcing: some SDK versions support tool_choice
        if force_file_search:
            run_kwargs["tool_choice"] = {"type": "file_search"}

        run = self.client.beta.threads.runs.create_and_poll(**run_kwargs)

        msgs = self.client.beta.threads.messages.list(thread_id=thread.id, order="desc", limit=10)
        assistant_msg = None
        for m in msgs.data:
            if m.role == "assistant":
                assistant_msg = m
                break

        if not assistant_msg:
            return AssistantAnswer(
                text="No assistant response was generated.",
                citations=[],
                raw_thread_id=thread.id,
                raw_run_id=getattr(run, "id", None),
            )

        text, citations = self._extract_text_and_citations(assistant_msg)

        return AssistantAnswer(
            text=text,
            citations=citations,
            raw_message_id=getattr(assistant_msg, "id", None),
            raw_thread_id=thread.id,
            raw_run_id=getattr(run, "id", None),
        )

    def _extract_text_and_citations(self, message_obj) -> Tuple[str, List[Dict[str, Any]]]:
        parts = []
        citations: List[Dict[str, Any]] = []

        content = getattr(message_obj, "content", []) or []
        for block in content:
            if getattr(block, "type", None) != "text":
                continue
            text_obj = getattr(block, "text", None)
            if not text_obj:
                continue

            value = getattr(text_obj, "value", "") or ""
            parts.append(value)

            annotations = getattr(text_obj, "annotations", []) or []
            for ann in annotations:
                if getattr(ann, "type", None) == "file_citation":
                    fc = getattr(ann, "file_citation", None)
                    file_id = getattr(fc, "file_id", None) if fc else None
                    citations.append(
                        {
                            "file_id": file_id,
                            "quote_text": getattr(ann, "text", None),
                            "start_index": getattr(ann, "start_index", None),
                            "end_index": getattr(ann, "end_index", None),
                        }
                    )

        # Best-effort file_id -> filename
        for c in citations:
            fid = c.get("file_id")
            if fid:
                try:
                    f = self.client.files.retrieve(fid)
                    c["filename"] = getattr(f, "filename", None)
                except Exception:
                    c["filename"] = None

        # De-duplicate citations
        uniq = []
        seen = set()
        for c in citations:
            key = (c.get("file_id"), c.get("start_index"), c.get("end_index"))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(c)

        return "\n\n".join(parts).strip(), uniq

    # ----------------------------
    # Instructions
    # ----------------------------

    def _default_instructions(self) -> str:
        return (
            "You are ARIS, a precision document QA assistant.\n"
            "Your ONLY job is to answer using information found via the file_search tool.\n\n"
            "Rules:\n"
            "1) ALWAYS use file_search before answering. If you did not search, you MUST search.\n"
            "2) If the answer is not in the documents, say you cannot find it in the provided documents.\n"
            "3) Be concise but specific.\n"
            "4) When you state a fact from documents, include citations produced by the system.\n"
            "5) Do not invent page numbers or filenames.\n"
        )