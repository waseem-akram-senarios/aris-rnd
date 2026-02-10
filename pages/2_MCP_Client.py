"""
MCP Client - Complete Interface for ARIS RAG MCP Server
All 18 MCP tools exposed through a premium Glassmorphism UI.

Tool categories:
- Query:      rag_quick_query, rag_research_query, rag_search
- Documents:  rag_ingest, rag_upload_document, rag_list_documents,
              rag_get_document, rag_update_document, rag_delete_document
- Indexes:    rag_list_indexes, rag_get_index_info, rag_delete_index
- Chunks:     rag_list_chunks, rag_get_chunk, rag_create_chunk,
              rag_update_chunk, rag_delete_chunk
- System:     rag_get_stats
"""

import streamlit as st
import sys
import os
import json
import time
import base64
import requests
from pathlib import Path
from datetime import datetime

# Add project root to path
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared.config.settings import ARISConfig

# Page configuration
st.set_page_config(
    page_title="MCP Client - ARIS RAG",
    page_icon="🔌",
    layout="wide"
)

# Apply the same CSS as the main app
from api.styles import get_custom_css
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Additional MCP-specific CSS
st.markdown("""
<style>
    .mcp-header {
        background: linear-gradient(135deg, rgba(16,185,129,.2) 0%, rgba(59,130,246,.2) 100%);
        border: 1px solid rgba(16,185,129,.3);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 1.5rem;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .mcp-header::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0; bottom: 0;
        background: radial-gradient(circle at 30% 50%, rgba(16,185,129,.12) 0%, transparent 50%),
                    radial-gradient(circle at 70% 50%, rgba(59,130,246,.12) 0%, transparent 50%);
        pointer-events: none;
    }
    .mcp-header h1 {
        font-size: 2.2rem; font-weight: 800;
        background: linear-gradient(135deg, #34d399, #60a5fa);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: .3rem; position: relative;
    }
    .mcp-header p { color: #94a3b8; font-size: 1rem; position: relative; }

    .status-card {
        background: rgba(30,41,59,.6);
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 12px; padding: 1rem;
        backdrop-filter: blur(10px);
    }
    .status-card.connected { border-color: rgba(16,185,129,.4); }
    .status-card h4 { color: #94a3b8; font-size: .82rem; font-weight: 500; margin-bottom: .4rem; }
    .status-card .value { font-size: .95rem; font-weight: 600; color: #f1f5f9; }
    .status-card .value.success { color: #34d399; }

    .tool-card {
        background: rgba(30,41,59,.6);
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem;
        border-left: 4px solid #3b82f6;
    }
    .tool-card.ingest   { border-left-color: #10b981; }
    .tool-card.search   { border-left-color: #8b5cf6; }
    .tool-card.docs     { border-left-color: #f59e0b; }
    .tool-card.indexes  { border-left-color: #ef4444; }
    .tool-card.system   { border-left-color: #06b6d4; }
    .tool-card h3 { color: #f1f5f9; font-size: 1.05rem; margin-bottom: .3rem; }
    .tool-card p  { color: #94a3b8; font-size: .85rem; }

    .answer-box {
        background: linear-gradient(135deg, rgba(59,130,246,.1), rgba(139,92,246,.1));
        border: 1px solid rgba(59,130,246,.3);
        border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem;
    }
    .answer-box h4 { color: #60a5fa; font-size: 1rem; margin-bottom: .6rem; }
    .answer-box .answer-text { color: #e2e8f0; line-height: 1.65; }

    .metrics-row { display: flex; gap: .75rem; margin-bottom: 1rem; }
    .metric-card {
        flex: 1; background: rgba(30,41,59,.6);
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 10px; padding: .85rem; text-align: center;
    }
    .metric-card .metric-value {
        font-size: 1.4rem; font-weight: 700;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .metric-card .metric-label { color: #94a3b8; font-size: .78rem; margin-top: .15rem; }

    .feature-badge {
        display: inline-flex; align-items: center; gap: .3rem;
        padding: .2rem .55rem;
        background: rgba(59,130,246,.15); border: 1px solid rgba(59,130,246,.3);
        border-radius: 999px; font-size: .72rem; color: #60a5fa;
        margin-right: .4rem; margin-bottom: .4rem;
    }
    .danger-zone {
        background: rgba(239,68,68,.08);
        border: 1px solid rgba(239,68,68,.25);
        border-radius: 12px; padding: 1rem; margin-top: .5rem;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE
# ============================================================================
for key, default in [
    ("mcp_results", []), ("mcp_history", []),
    ("pending_search_query", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ============================================================================
# MCP SERVER URL
# ============================================================================
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8503")
if os.getenv("SERVICE_TYPE") == "ui":
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp:8503")

TIMEOUT_SHORT = 15
TIMEOUT_LONG = 300


# ============================================================================
# MCP HTTP CLIENT FUNCTIONS
# ============================================================================

def _get(path, timeout=TIMEOUT_SHORT):
    try:
        r = requests.get(f"{MCP_SERVER_URL}{path}", timeout=timeout)
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Cannot connect to MCP server at {MCP_SERVER_URL}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _post(path, body=None, timeout=TIMEOUT_LONG):
    try:
        r = requests.post(f"{MCP_SERVER_URL}{path}", json=body, timeout=timeout)
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Cannot connect to MCP server at {MCP_SERVER_URL}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _put(path, body=None, timeout=TIMEOUT_SHORT):
    try:
        r = requests.put(f"{MCP_SERVER_URL}{path}", json=body, timeout=timeout)
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Cannot connect to MCP server at {MCP_SERVER_URL}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _delete(path, timeout=TIMEOUT_SHORT):
    try:
        r = requests.delete(f"{MCP_SERVER_URL}{path}", timeout=timeout)
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"Cannot connect to MCP server at {MCP_SERVER_URL}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Convenience wrappers
def mcp_search(**kw):       return _post("/api/search", kw)
def mcp_ingest(**kw):       return _post("/api/ingest", kw)
def mcp_upload(**kw):        return _post("/api/upload", kw)
def mcp_list_documents():    return _get("/api/documents")
def mcp_get_document(did):   return _get(f"/api/documents/{did}")
def mcp_update_document(did, body): return _put(f"/api/documents/{did}", body)
def mcp_delete_document(did): return _delete(f"/api/documents/{did}")
def mcp_get_stats():         return _get("/api/stats")
def mcp_list_indexes():      return _get("/api/indexes")
def mcp_get_index(idx):      return _get(f"/api/indexes/{idx}")
def mcp_delete_index(idx):   return _delete(f"/api/indexes/{idx}")
def mcp_list_chunks(idx, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
    return _get(f"/api/indexes/{idx}/chunks?{qs}" if qs else f"/api/indexes/{idx}/chunks")
def mcp_get_chunk(idx, cid): return _get(f"/api/indexes/{idx}/chunks/{cid}")
def mcp_create_chunk(idx, body): return _post(f"/api/indexes/{idx}/chunks", body)
def mcp_update_chunk(idx, cid, body): return _put(f"/api/indexes/{idx}/chunks/{cid}", body)
def mcp_delete_chunk(idx, cid): return _delete(f"/api/indexes/{idx}/chunks/{cid}")


def check_mcp_server_health():
    try:
        r = requests.get(f"{MCP_SERVER_URL}/health", timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _log_history(tool, inp, result=None, elapsed=0, **extra):
    st.session_state.mcp_history.append({
        "tool": tool, "timestamp": datetime.now().isoformat(),
        "input": inp, "result": result, "elapsed": elapsed, **extra
    })


def _confidence_icon(c):
    if c >= 70: return "🟢"
    if c >= 40: return "🟡"
    return "🔴"


# ============================================================================
# HEADER
# ============================================================================
st.markdown("""
<div class="mcp-header">
    <h1>🔌 MCP Client</h1>
    <p>Complete management interface for ARIS RAG MCP Server — 18 tools</p>
</div>
""", unsafe_allow_html=True)

# Status row
c1, c2, c3 = st.columns(3)
with c1:
    health = check_mcp_server_health()
    if health:
        total = health.get("total_tools", 18)
        st.markdown(f"""<div class="status-card connected">
            <h4>📡 MCP Server</h4>
            <div class="value success">✓ Connected — {total} tools</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="status-card">
            <h4>📡 MCP Server</h4>
            <div class="value">✗ Unreachable ({MCP_SERVER_URL})</div>
        </div>""", unsafe_allow_html=True)

with c2:
    st.markdown("""<div class="status-card">
        <h4>🔧 Tool Categories</h4>
        <div class="value">Query · Documents · Indexes · Chunks · System</div>
    </div>""", unsafe_allow_html=True)

with c3:
    st.markdown("""<div class="status-card">
        <h4>✨ Features</h4>
        <div>
            <span class="feature-badge">Hybrid Search</span>
            <span class="feature-badge">Reranking</span>
            <span class="feature-badge">Agentic RAG</span>
            <span class="feature-badge">Full CRUD</span>
        </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================================
# TABS
# ============================================================================
tab_search, tab_ingest, tab_docs, tab_indexes, tab_chunks, tab_system, tab_history = st.tabs([
    "🔍 Search", "📥 Add Documents", "📄 Documents",
    "🗂️ Indexes", "🧩 Chunks", "📊 System", "📜 History"
])

# ============================================================================
# TAB 1 — SEARCH
# ============================================================================
with tab_search:
    st.markdown("""<div class="tool-card search">
        <h3>🔍 Search Documents</h3>
        <p>Query the RAG system with hybrid search, reranking, and Agentic RAG.</p>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        default_q = st.session_state.pending_search_query or ""
        if st.session_state.pending_search_query:
            st.session_state.pending_search_query = None
        query = st.text_area("Search Query", value=default_q, height=100,
                             placeholder="Enter your question...", key="search_query")
        ex = st.columns(4)
        for i, (label, q) in enumerate([
            ("📋 Maintenance", "What are the maintenance procedures?"),
            ("🔧 Troubleshoot", "How to troubleshoot common errors?"),
            ("📖 Overview", "Give me an overview of the system"),
            ("📜 Policy", "What is the attendance policy?"),
        ]):
            with ex[i]:
                if st.button(label, use_container_width=True):
                    st.session_state.pending_search_query = q
                    st.rerun()

    with col2:
        st.markdown("#### Options")
        k = st.slider("Results (k)", 1, 20, 5)
        search_mode = st.selectbox("Search Mode", ["hybrid", "semantic", "keyword"])
        with st.expander("⚙️ Advanced"):
            use_agentic = st.checkbox("Agentic RAG", value=True)
            include_answer = st.checkbox("Generate Answer", value=True)
        st.markdown("#### Filters")
        f_domain = st.selectbox("Domain", ["", "ticket", "machine_manual", "policy", "troubleshooting"])
        f_source = st.text_input("Source", placeholder="document.pdf")

    if st.button("🔍 Search", type="primary", use_container_width=True, key="btn_search"):
        if not query:
            st.error("Please enter a search query")
        else:
            filters = {}
            if f_domain: filters["domain"] = f_domain
            if f_source: filters["source"] = f_source
            with st.spinner("Searching..." + (" (Agentic RAG)" if use_agentic else "")):
                t0 = time.time()
                result = mcp_search(query=query, filters=filters or None, k=k,
                                    search_mode=search_mode,
                                    use_agentic_rag=use_agentic,
                                    include_answer=include_answer)
                elapsed = time.time() - t0

                if result.get("success"):
                    ai = result.get("accuracy_info", {})
                    st.markdown(f"""<div class="metrics-row">
                        <div class="metric-card"><div class="metric-value">{result.get('total_results',0)}</div><div class="metric-label">Results</div></div>
                        <div class="metric-card"><div class="metric-value">{result.get('search_mode','N/A')}</div><div class="metric-label">Mode</div></div>
                        <div class="metric-card"><div class="metric-value">{ai.get('sub_queries_generated',0)}</div><div class="metric-label">Sub-queries</div></div>
                        <div class="metric-card"><div class="metric-value">{elapsed:.2f}s</div><div class="metric-label">Time</div></div>
                    </div>""", unsafe_allow_html=True)

                    if include_answer and result.get("answer"):
                        st.markdown(f"""<div class="answer-box">
                            <h4>💡 Answer</h4>
                            <div class="answer-text">{result['answer']}</div>
                        </div>""", unsafe_allow_html=True)

                    for i, ch in enumerate(result.get("results", [])):
                        conf = ch.get("confidence", 0)
                        with st.expander(f"{_confidence_icon(conf)} **#{i+1}** — {ch.get('source','?')} (p{ch.get('page','?')}) — {conf:.0f}%", expanded=i < 3):
                            st.markdown(ch.get("snippet", ch.get("content", ""))[:500])
                            if ch.get("metadata"):
                                with st.expander("Metadata"):
                                    st.json(ch["metadata"])

                    with st.expander("📊 Accuracy Info"):
                        st.json(ai)
                    _log_history("rag_search", {"query": query[:50], "k": k},
                                 result_count=result.get("total_results", 0), elapsed=elapsed)
                else:
                    st.error(f"❌ {result.get('error', 'Unknown error')}")

# ============================================================================
# TAB 2 — ADD DOCUMENTS
# ============================================================================
with tab_ingest:
    st.markdown("""<div class="tool-card ingest">
        <h3>📥 Add Documents to RAG System</h3>
        <p>Ingest plain text, S3 URIs, or upload files (PDF, DOCX, TXT, MD, HTML).</p>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        ctype = st.radio("Content Type", ["Plain Text", "S3 URI", "Upload File"],
                         horizontal=True, key="ingest_type")
        content = None
        uploaded_file = None
        if ctype == "Plain Text":
            content = st.text_area("Content", height=200, placeholder="Paste text here...", key="ingest_content")
        elif ctype == "S3 URI":
            content = st.text_input("S3 URI", placeholder="s3://bucket/path/doc.pdf", key="ingest_s3")
        else:
            uploaded_file = st.file_uploader("Upload Document",
                                             type=["pdf","docx","doc","txt","md","html"], key="upload_file")
            if uploaded_file:
                st.success(f"✅ Selected: **{uploaded_file.name}** ({uploaded_file.size/1024:.1f} KB)")

    with col2:
        st.markdown("#### Metadata")
        domain = st.selectbox("Domain", ["","ticket","machine_manual","policy","troubleshooting","other"], key="ing_domain")
        language = st.selectbox("Language", ["en","es","de","fr","it","pt","ru","ja","ko","zh","ar"], key="ing_lang")
        source_id = st.text_input("Source ID", placeholder="e.g., manual_v2.pdf", key="ing_source")
        custom_meta = st.text_area("Custom JSON", placeholder='{"version":"2.0"}', height=70, key="ing_meta")

    if st.button("📥 Ingest Document", type="primary", use_container_width=True, key="btn_ingest"):
        has = uploaded_file if ctype == "Upload File" else (content and content.strip())
        if not has:
            st.error("Please provide content to ingest")
        else:
            meta = {}
            if domain: meta["domain"] = domain
            if language: meta["language"] = language
            if source_id: meta["source"] = source_id
            if custom_meta:
                try:
                    meta.update(json.loads(custom_meta))
                except Exception:
                    st.error("Invalid JSON in custom metadata"); st.stop()

            if ctype == "Upload File":
                with st.spinner(f"Processing {uploaded_file.name}..."):
                    t0 = time.time()
                    fb = uploaded_file.read()
                    ext = uploaded_file.name.lower().rsplit(".", 1)[-1]
                    fc = base64.b64encode(fb).decode() if ext in ("pdf","docx","doc") else fb.decode("utf-8", errors="replace")
                    result = mcp_upload(file_content=fc, filename=uploaded_file.name, metadata=meta or None)
                    el = time.time() - t0
                    if result.get("success"):
                        st.success("✅ Document uploaded!")
                        ca, cb, cc, cd = st.columns(4)
                        ca.metric("Doc ID", result.get("document_id","?")[:12]+"...")
                        cb.metric("Chunks", result.get("chunks_created",0))
                        cc.metric("Pages", result.get("pages_extracted","N/A"))
                        cd.metric("Time", f"{el:.1f}s")
                        with st.expander("📋 Full Response"): st.json(result)
                        _log_history("rag_upload_document", {"filename": uploaded_file.name}, result, el)
                    else:
                        st.error(f"❌ {result.get('error', result.get('message','Unknown'))}")
            else:
                with st.spinner("Ingesting..."):
                    t0 = time.time()
                    result = mcp_ingest(content=content, metadata=meta or None)
                    el = time.time() - t0
                    if result.get("success"):
                        st.success("✅ Ingested!")
                        ca, cb, cc = st.columns(3)
                        ca.metric("Doc ID", result.get("document_id","?")[:12]+"...")
                        cb.metric("Chunks", result.get("chunks_created",0))
                        cc.metric("Time", f"{el:.1f}s")
                        _log_history("rag_ingest", {"content_len": len(content)}, result, el)
                    else:
                        st.error(f"❌ {result.get('error', result.get('message','Unknown'))}")

# ============================================================================
# TAB 3 — DOCUMENTS
# ============================================================================
with tab_docs:
    st.markdown("""<div class="tool-card docs">
        <h3>📄 Document Management</h3>
        <p>List, view details, update metadata, or delete documents.</p>
    </div>""", unsafe_allow_html=True)

    if st.button("🔄 Load Documents", use_container_width=True, key="btn_load_docs"):
        with st.spinner("Loading..."):
            result = mcp_list_documents()
        if result.get("success"):
            docs = result.get("documents", [])
            st.info(f"**{result.get('total', len(docs))}** documents — **{result.get('total_chunks',0)}** total chunks")

            for doc in docs:
                did = doc.get("document_id", doc.get("id", "?"))
                dname = doc.get("document_name", doc.get("name", "Untitled"))
                status = doc.get("status", "unknown")
                chunks = doc.get("chunks_created", doc.get("chunks", "?"))
                lang = doc.get("language", "?")
                status_icon = "🟢" if status == "processed" else "🟡" if status == "processing" else "⚪"

                with st.expander(f"{status_icon} **{dname}** — {chunks} chunks — {lang}", expanded=False):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.code(did, language=None)
                        st.caption(f"Status: {status} | Language: {lang} | Chunks: {chunks}")
                        # Get details button
                        if st.button(f"📋 Details", key=f"det_{did}"):
                            detail = mcp_get_document(did)
                            if detail.get("success"):
                                st.json(detail.get("document", detail))
                            else:
                                st.error(detail.get("error", "Failed"))

                    with c2:
                        st.markdown("**Update Metadata**")
                        new_name = st.text_input("Name", value=dname, key=f"name_{did}")
                        new_status = st.selectbox("Status", ["processed","archived","pending"],
                                                  index=0, key=f"stat_{did}")
                        if st.button("💾 Update", key=f"upd_{did}"):
                            updates = {}
                            if new_name != dname: updates["document_name"] = new_name
                            if new_status != status: updates["status"] = new_status
                            if updates:
                                r = mcp_update_document(did, updates)
                                if r.get("success"):
                                    st.success("Updated!")
                                    _log_history("rag_update_document", {"id": did[:12], **updates})
                                else:
                                    st.error(r.get("error", "Failed"))
                            else:
                                st.info("No changes")

                        st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
                        if st.button("🗑️ Delete", key=f"del_{did}", type="secondary"):
                            r = mcp_delete_document(did)
                            if r.get("success"):
                                st.success(f"Deleted: {dname}")
                                _log_history("rag_delete_document", {"id": did[:12], "name": dname})
                                st.rerun()
                            else:
                                st.error(r.get("error", "Failed"))
                        st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error(f"❌ {result.get('error', 'Failed to load documents')}")

# ============================================================================
# TAB 4 — INDEXES
# ============================================================================
with tab_indexes:
    st.markdown("""<div class="tool-card indexes">
        <h3>🗂️ Vector Index Management</h3>
        <p>Browse, inspect, and manage vector indexes in OpenSearch.</p>
    </div>""", unsafe_allow_html=True)

    if st.button("🔄 Load Indexes", use_container_width=True, key="btn_load_idx"):
        with st.spinner("Loading..."):
            result = mcp_list_indexes()
        if result.get("success"):
            indexes = result.get("indexes", [])
            st.info(f"**{result.get('total', len(indexes))}** indexes found")

            # Filter to aris-doc indexes
            aris_indexes = [ix for ix in indexes if isinstance(ix, dict) and "aris-doc" in str(ix.get("index",""))]
            other_indexes = [ix for ix in indexes if isinstance(ix, dict) and "aris-doc" not in str(ix.get("index",""))]

            if aris_indexes:
                st.markdown("#### Document Indexes")
                for ix in aris_indexes:
                    name = ix.get("index", ix.get("name", "?"))
                    docs_count = ix.get("docs.count", ix.get("doc_count", "?"))
                    store_size = ix.get("store.size", ix.get("size", "?"))
                    with st.expander(f"📁 **{name}** — {docs_count} docs — {store_size}"):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            if st.button("ℹ️ Details", key=f"ixd_{name}"):
                                info = mcp_get_index(name)
                                st.json(info)
                        with c2:
                            st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
                            if st.button("🗑️ Delete Index", key=f"ixdel_{name}", type="secondary"):
                                r = mcp_delete_index(name)
                                if r.get("success"):
                                    st.success(f"Deleted: {name}")
                                    _log_history("rag_delete_index", {"index": name})
                                    st.rerun()
                                else:
                                    st.error(r.get("error", "Failed"))
                            st.markdown('</div>', unsafe_allow_html=True)

            if other_indexes:
                with st.expander(f"⚙️ System Indexes ({len(other_indexes)})"):
                    for ix in other_indexes:
                        name = ix.get("index", ix.get("name", "?"))
                        st.text(f"  {name}")
        else:
            st.error(f"❌ {result.get('error', 'Failed')}")

# ============================================================================
# TAB 5 — CHUNKS
# ============================================================================
with tab_chunks:
    st.markdown("""<div class="tool-card">
        <h3>🧩 Chunk Management</h3>
        <p>Browse, create, edit, and delete individual vector chunks within indexes.</p>
    </div>""", unsafe_allow_html=True)

    idx_name = st.text_input("Index Name", placeholder="aris-doc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                             key="chunk_idx")

    if idx_name:
        chunk_action = st.radio("Action", ["List Chunks", "Get Chunk", "Create Chunk", "Update Chunk", "Delete Chunk"],
                                horizontal=True, key="chunk_action")

        if chunk_action == "List Chunks":
            c1, c2, c3 = st.columns(3)
            with c1: offset = st.number_input("Offset", value=0, min_value=0, key="ch_off")
            with c2: limit = st.number_input("Limit", value=20, min_value=1, max_value=100, key="ch_lim")
            with c3: src_filter = st.text_input("Source filter", key="ch_src")

            if st.button("📋 List Chunks", use_container_width=True, key="btn_list_chunks"):
                with st.spinner("Loading..."):
                    result = mcp_list_chunks(idx_name, offset=offset, limit=limit,
                                             source=src_filter if src_filter else None)
                if result.get("success"):
                    chunks = result.get("chunks", [])
                    st.info(f"**{result.get('total', len(chunks))}** total chunks (showing {len(chunks)})")
                    for i, ch in enumerate(chunks):
                        cid = ch.get("id", ch.get("_id", "?"))
                        text_preview = ch.get("text", ch.get("content", ""))[:120]
                        src = ch.get("source", "?")
                        pg = ch.get("page", "?")
                        with st.expander(f"**#{offset+i+1}** — {src} (p{pg}) — `{cid[:20]}...`"):
                            st.text(text_preview + "...")
                            st.code(cid, language=None)
                else:
                    st.error(result.get("error", "Failed"))

        elif chunk_action == "Get Chunk":
            cid = st.text_input("Chunk ID", key="ch_get_id")
            if st.button("🔍 Get Chunk", key="btn_get_chunk") and cid:
                result = mcp_get_chunk(idx_name, cid)
                if result.get("success"):
                    st.json(result.get("chunk", result))
                else:
                    st.error(result.get("error", "Failed"))

        elif chunk_action == "Create Chunk":
            ch_text = st.text_area("Text Content", height=150, key="ch_create_text")
            c1, c2 = st.columns(2)
            with c1: ch_src = st.text_input("Source", value="manual_entry", key="ch_create_src")
            with c2: ch_pg = st.number_input("Page", value=1, min_value=1, key="ch_create_pg")
            ch_meta = st.text_area("Metadata (JSON)", placeholder='{"key":"value"}', height=60, key="ch_create_meta")

            if st.button("➕ Create Chunk", type="primary", use_container_width=True, key="btn_create_chunk"):
                if not ch_text:
                    st.error("Text is required")
                else:
                    body = {"text": ch_text, "source": ch_src, "page": ch_pg}
                    if ch_meta:
                        try:
                            body["metadata"] = json.loads(ch_meta)
                        except Exception:
                            st.error("Invalid JSON"); st.stop()
                    result = mcp_create_chunk(idx_name, body)
                    if result.get("success"):
                        st.success(f"✅ Created chunk: `{result.get('chunk_id','?')}`")
                        _log_history("rag_create_chunk", {"index": idx_name, "text": ch_text[:50]})
                    else:
                        st.error(result.get("error", "Failed"))

        elif chunk_action == "Update Chunk":
            cid = st.text_input("Chunk ID", key="ch_upd_id")
            new_text = st.text_area("New Text (leave empty to skip)", height=100, key="ch_upd_text")
            new_pg = st.number_input("New Page (0 = skip)", value=0, min_value=0, key="ch_upd_pg")
            new_meta = st.text_area("New Metadata (JSON, leave empty to skip)", height=60, key="ch_upd_meta")

            if st.button("💾 Update Chunk", type="primary", use_container_width=True, key="btn_upd_chunk") and cid:
                body = {}
                if new_text: body["text"] = new_text
                if new_pg > 0: body["page"] = new_pg
                if new_meta:
                    try:
                        body["metadata"] = json.loads(new_meta)
                    except Exception:
                        st.error("Invalid JSON"); st.stop()
                if body:
                    result = mcp_update_chunk(idx_name, cid, body)
                    if result.get("success"):
                        st.success(f"✅ Updated chunk `{cid[:20]}...`")
                        _log_history("rag_update_chunk", {"chunk_id": cid[:20], **body})
                    else:
                        st.error(result.get("error", "Failed"))
                else:
                    st.info("No changes provided")

        elif chunk_action == "Delete Chunk":
            cid = st.text_input("Chunk ID to delete", key="ch_del_id")
            st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
            if st.button("🗑️ Delete Chunk", type="secondary", use_container_width=True, key="btn_del_chunk") and cid:
                result = mcp_delete_chunk(idx_name, cid)
                if result.get("success"):
                    st.success(f"✅ Deleted chunk `{cid[:20]}...`")
                    _log_history("rag_delete_chunk", {"index": idx_name, "chunk_id": cid[:20]})
                else:
                    st.error(result.get("error", "Failed"))
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Enter an index name above to manage its chunks.")

# ============================================================================
# TAB 6 — SYSTEM
# ============================================================================
with tab_system:
    st.markdown("""<div class="tool-card system">
        <h3>📊 System Statistics & Monitoring</h3>
        <p>View overall RAG system stats, service health, and sync status.</p>
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📊 Load System Stats", use_container_width=True, key="btn_stats"):
            with st.spinner("Loading stats..."):
                result = mcp_get_stats()
            if result.get("success"):
                stats = result.get("stats", result)
                # Display processing stats
                proc = stats.get("processing", {})
                if proc:
                    st.markdown("#### Processing")
                    mc = st.columns(4)
                    mc[0].metric("Documents", proc.get("total_documents", 0))
                    mc[1].metric("Total Chunks", proc.get("total_chunks", 0))
                    mc[2].metric("Total Pages", proc.get("total_pages", 0))
                    mc[3].metric("Total Tokens", f"{proc.get('total_tokens', 0):,}")

                # Query stats
                queries = stats.get("queries", {})
                if queries:
                    st.markdown("#### Queries")
                    mc = st.columns(3)
                    mc[0].metric("Total Queries", queries.get("total_queries", 0))
                    mc[1].metric("Avg Response", f"{queries.get('average_response_time', 0):.2f}s")
                    mc[2].metric("Avg Accuracy", f"{queries.get('average_accuracy', 0):.1f}%")

                with st.expander("📋 Full Stats JSON"):
                    st.json(stats)
            else:
                st.error(result.get("error", "Failed"))

    with c2:
        if st.button("🏥 Service Health", use_container_width=True, key="btn_health"):
            health = check_mcp_server_health()
            if health:
                st.json(health)
            else:
                st.error("MCP server unreachable")

        if st.button("🔄 Force Sync", use_container_width=True, key="btn_sync"):
            result = _post("/sync/force", timeout=15)
            if result.get("success"):
                st.success("Sync completed!")
                st.json(result)
            else:
                st.error(result.get("error", "Failed"))

# ============================================================================
# TAB 7 — HISTORY
# ============================================================================
with tab_history:
    st.markdown("### 📜 Execution History")
    if st.session_state.mcp_history:
        if st.button("🗑️ Clear History", key="btn_clear_hist"):
            st.session_state.mcp_history = []
            st.rerun()

        icons = {"rag_ingest":"📥", "rag_upload_document":"📤", "rag_search":"🔍",
                 "rag_list_documents":"📄", "rag_get_document":"📋",
                 "rag_update_document":"💾", "rag_delete_document":"🗑️",
                 "rag_list_indexes":"🗂️", "rag_delete_index":"🗑️",
                 "rag_create_chunk":"➕", "rag_update_chunk":"💾",
                 "rag_delete_chunk":"🗑️", "rag_get_stats":"📊"}

        for i, entry in enumerate(reversed(st.session_state.mcp_history)):
            icon = icons.get(entry["tool"], "🔧")
            with st.expander(f"{icon} **{entry['tool']}** — {entry['timestamp'][:19]}", expanded=i < 2):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Input:**")
                    st.json(entry.get("input", {}))
                with c2:
                    st.markdown("**Result:**")
                    el = entry.get("elapsed", 0)
                    if el:
                        st.write(f"⏱️ Time: {el:.2f}s")
                    rc = entry.get("result_count")
                    if rc is not None:
                        st.write(f"📊 Results: {rc}")
                    r = entry.get("result")
                    if isinstance(r, dict) and r.get("success") is not None:
                        st.write(f"✅ Success: {r['success']}")
    else:
        st.info("📭 No executions yet. Use the tabs above to test MCP tools.")

# Footer
st.divider()
st.markdown(f"""
<div style="text-align:center; color:#64748b; font-size:.82rem;">
    <p>🔌 MCP Client for ARIS RAG System — 18 tools across 5 categories</p>
    <p>Server: <code>{MCP_SERVER_URL}</code></p>
</div>
""", unsafe_allow_html=True)
