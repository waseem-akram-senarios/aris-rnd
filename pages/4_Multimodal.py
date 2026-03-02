import sys
from pathlib import Path
import json
import streamlit as st

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from api.styles import get_custom_css
from services.mm_rag.pipeline import MultimodalRAGPipeline

st.set_page_config(page_title="ARIS Multimodal RAG", page_icon="🖼️", layout="wide")
st.markdown(get_custom_css(), unsafe_allow_html=True)

st.markdown("""
<div class="hero-header">
    <div class="hero-title">ARIS Multimodal RAG</div>
    <div class="hero-subtitle">PyMuPDF page render · OpenAI Vision extraction · Page-grounded citations</div>
</div>
""", unsafe_allow_html=True)

STORAGE_ROOT = str(Path(_PROJECT_ROOT) / "storage" / "mm_rag")

if "mm_pipeline" not in st.session_state:
    st.session_state.mm_pipeline = MultimodalRAGPipeline(storage_root=STORAGE_ROOT)

pipe: MultimodalRAGPipeline = st.session_state.mm_pipeline

with st.sidebar:
    st.markdown("### Dataset")
    dataset_name = st.text_input("Dataset name", value=st.session_state.get("mm_dataset", "default")).strip() or "default"
    st.session_state.mm_dataset = dataset_name

    st.markdown("---")
    st.markdown("### Retrieval")
    top_k = st.slider("Top-K chunks", min_value=2, max_value=12, value=6, step=1)

st.markdown("## Existing multimodal datasets")
ds = pipe.registry.list()
if ds:
    st.dataframe(
        [{"dataset": v.dataset_name, "created_at": v.created_at, "updated_at": v.updated_at} for v in ds.values()],
        use_container_width=True,
    )
else:
    st.info("No multimodal datasets yet.")

st.markdown("---")
st.markdown("## 1) Ingest PDFs with vision (page-by-page)")
uploads = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)

col1, col2 = st.columns([1, 1])
ingest_btn = col1.button("Ingest", type="primary", disabled=not uploads)
if col2.button("Reset local dataset registry entry"):
    pipe.registry.delete(dataset_name)
    st.success(f"Deleted local registry entry for '{dataset_name}' (index files remain on disk).")

if ingest_btn and uploads:
    files = [(f.name, f.getvalue()) for f in uploads]
    with st.spinner("Rendering pages + vision extracting text + indexing..."):
        res = pipe.ingest_files(dataset_name, files)
    st.success("Ingestion complete.")
    st.code(json.dumps(res, indent=2), language="json")

st.markdown("---")
st.markdown("## 2) Ask (citations include page numbers)")
q = st.text_area("Question", height=120, placeholder="Ask something about the ingested PDFs...")

ask_btn = st.button("Ask", type="primary", disabled=not q.strip())
if ask_btn and q.strip():
    with st.spinner("Retrieving relevant pages + answering..."):
        out = pipe.ask(dataset_name, q.strip(), k=top_k)

    st.markdown("### Answer")
    st.write(out["answer"])

    st.markdown("### Citations (page-grounded)")
    if out["citations"]:
        st.dataframe(out["citations"], use_container_width=True)
    else:
        st.caption("No citations returned (likely no relevant chunks were retrieved).")