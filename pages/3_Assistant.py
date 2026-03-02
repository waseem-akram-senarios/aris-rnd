"""
ARIS Assistant Mode - OpenAI Assistants API (file_search + vector stores)

This is an additive Streamlit page. It does NOT modify existing ingestion/retrieval logic.
"""
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
from typing import List, Tuple
import json
import time

from api.styles import get_custom_css
from services.assistant_rag.client import AssistantRAGClient

# Page configuration
st.set_page_config(
    page_title="ARIS Assistant - Assistants API RAG",
    page_icon="🧠",
    layout="wide",
)

st.markdown(get_custom_css(), unsafe_allow_html=True)

st.markdown("""
<div class="hero-header">
    <div class="hero-title">ARIS Assistant Mode</div>
    <div class="hero-subtitle">OpenAI Assistants API · File Search · Vector Stores</div>
</div>
""", unsafe_allow_html=True)

REGISTRY_PATH = str(Path(_PROJECT_ROOT) / "storage" / "assistant_registry.json")

if "assistant_client" not in st.session_state:
    st.session_state.assistant_client = None

def get_client() -> AssistantRAGClient:
    if st.session_state.assistant_client is None:
        st.session_state.assistant_client = AssistantRAGClient(registry_path=REGISTRY_PATH)
    return st.session_state.assistant_client

with st.sidebar:
    st.markdown("### 🧩 Assistant Workspace")
    dataset_name = st.text_input(
        "Dataset name",
        value=st.session_state.get("assistant_dataset_name", "default"),
        help="One dataset = one Assistant + one Vector Store (Assistants API constraint).",
    ).strip() or "default"
    st.session_state.assistant_dataset_name = dataset_name

    model = st.text_input(
        "Model",
        value=st.session_state.get("assistant_model", "gpt-4o"),
        help="Model used by the assistant (e.g., gpt-4o).",
    ).strip() or "gpt-4o"
    st.session_state.assistant_model = model

    force_search = st.checkbox(
        "Force file_search tool",
        value=True,
        help="Best-effort: requests the run to use file_search. Some SDK versions may ignore this.",
    )

    st.markdown("---")
    st.markdown("### 🗂️ Registry")
    st.button("Refresh dataset list")

try:
    client = get_client()
except Exception as e:
    st.error(str(e))
    st.stop()

datasets = client.registry.list_datasets()
st.markdown("### Existing datasets")
if datasets:
    st.dataframe(
        [
            {
                "dataset": ds.dataset_name,
                "assistant_id": ds.assistant_id,
                "vector_store_id": ds.vector_store_id,
                "model": ds.model,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ds.updated_at)),
            }
            for ds in datasets.values()
        ],
        use_container_width=True,
    )
else:
    st.info("No datasets yet. Create one by uploading files below.")

st.markdown("---")

st.markdown("## 1) Upload documents to Assistant vector store")
uploads = st.file_uploader(
    "Upload PDFs / DOCX / TXT (multiple allowed)",
    type=["pdf", "txt", "docx", "md", "rtf"],
    accept_multiple_files=True,
)

colA, colB = st.columns([1, 1])
with colA:
    do_upload = st.button("Upload to dataset", type="primary", disabled=not uploads)
with colB:
    if st.button("Reset local dataset entry"):
        client.delete_dataset_local(dataset_name)
        st.success(f"Deleted local registry entry for '{dataset_name}'. (Cloud objects not deleted.)")

if do_upload and uploads:
    with st.spinner("Uploading and indexing files in OpenAI vector store..."):
        files: List[Tuple[str, bytes]] = [(f.name, f.getvalue()) for f in uploads]
        res = client.upload_files_to_dataset(dataset_name=dataset_name, uploaded_files=files, model=model)
    st.success("Upload complete.")
    st.code(json.dumps(res, indent=2), language="json")

st.markdown("---")

st.markdown("## 2) Ask questions (Assistant will search the uploaded docs)")
question = st.text_area(
    "Question",
    value="",
    height=120,
    placeholder="Ask something about your uploaded documents...",
)

ask_btn = st.button("Ask", type="primary", disabled=not question.strip())

if ask_btn and question.strip():
    with st.spinner("Running Assistant (file_search)..."):
        ans = client.ask(
            dataset_name=dataset_name,
            question=question.strip(),
            model=model,
            force_file_search=force_search,
        )

    st.markdown("### Answer")
    st.write(ans.text or "")

    st.markdown("### Citations (best-effort)")
    if ans.citations:
        st.dataframe(ans.citations, use_container_width=True)
    else:
        st.caption(
            "No file citations were returned. This can happen if the assistant answered without using "
            "file_search or if the SDK did not expose annotations."
        )

    with st.expander("Debug IDs"):
        st.code(
            json.dumps(
                {
                    "thread_id": ans.raw_thread_id,
                    "run_id": ans.raw_run_id,
                    "message_id": ans.raw_message_id,
                },
                indent=2,
            ),
            language="json",
        )

st.markdown("""
--- 
### Notes / limitations
- Assistants API supports **one vector store per assistant**, so this page uses **one assistant per dataset**.
- For scanned image-only PDFs, quality usually improves if you OCR them before upload (e.g., OCRmyPDF) so the vector store gets real text.
""")