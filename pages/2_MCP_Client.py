"""
MCP Client - Complete Interface for ARIS RAG MCP Server v5
3 MCP tools exposed through a premium Glassmorphism UI.

Tools:
- retrieval   — AI-powered document search with hybrid search + FlashRank reranking
- ingestion   — Full document lifecycle: docs, chunks, and indexes
- monitoring  — System statistics, health metrics, and performance monitoring

Improvements v5:
- Confirmation dialogs on all destructive operations
- Index dropdown auto-populated in chunk management
- Persistent execution history (survives page reloads)
- Consolidated System + Server into a single tab
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
_HISTORY_FILE = os.path.join(_PROJECT_ROOT, "data", "mcp_history.json")

def _load_persistent_history() -> list:
    """Load execution history from disk (survives page reloads)."""
    try:
        if os.path.exists(_HISTORY_FILE):
            with open(_HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_persistent_history(history: list):
    """Persist execution history to disk (keep last 200 entries)."""
    try:
        os.makedirs(os.path.dirname(_HISTORY_FILE), exist_ok=True)
        with open(_HISTORY_FILE, "w") as f:
            json.dump(history[-200:], f, indent=2, default=str)
    except Exception:
        pass


for key, default in [
    ("mcp_results", []),
    ("pending_search_query", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# Load persistent history on first run
if "mcp_history" not in st.session_state:
    st.session_state.mcp_history = _load_persistent_history()

# Confirmation state for delete dialogs
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = {}

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
    """Check MCP server health with retry logic for startup race conditions."""
    for attempt in range(3):
        try:
            r = requests.get(f"{MCP_SERVER_URL}/health", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            if attempt < 2:
                time.sleep(1)  # Brief pause between retries
            else:
                # Log on final failure only (avoids noisy logs during normal startup)
                print(f"MCP Health check failed: {e}")
    return None


def _log_history(tool, inp, result=None, elapsed=0, **extra):
    entry = {
        "tool": tool, "timestamp": datetime.now().isoformat(),
        "input": inp, "result": result, "elapsed": elapsed, **extra
    }
    st.session_state.mcp_history.append(entry)
    _save_persistent_history(st.session_state.mcp_history)


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
    <p>Document management &amp; AI-powered search — 3 tools</p>
</div>
""", unsafe_allow_html=True)

# Status row
c1, c2, c3 = st.columns(3)
with c1:
    health = check_mcp_server_health()
    if health:
        total = health.get("total_tools", 5)
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
        <h4>🔧 Tools</h4>
        <div class="value">Search · Documents · System Info</div>
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
tab_search, tab_ingest, tab_docs, tab_system, tab_history = st.tabs([
    "🔍 Search", "📥 Add Documents", "📄 Documents",
    "📊 System & Server", "📜 History"
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
                    _log_history("retrieval", {"query": query[:50], "k": k, "mode": "search"},
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
                        _log_history("ingestion", {"action": "create", "filename": uploaded_file.name}, result, el)
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
                        _log_history("ingestion", {"action": "create", "content_len": len(content)}, result, el)
                    else:
                        st.error(f"❌ {result.get('error', result.get('message','Unknown'))}")

# ============================================================================
# TAB 3 — DOCUMENTS (unified: docs + chunks + indexes)
# ============================================================================
with tab_docs:
    st.markdown("""<div class="tool-card docs">
        <h3>📄 Document Management</h3>
        <p>Manage documents, chunks, and indexes — all in one place.</p>
    </div>""", unsafe_allow_html=True)

    doc_sub1, doc_sub2, doc_sub3 = st.tabs(["📄 Documents", "🧩 Chunks", "🗂️ Indexes"])

    # --- Sub-tab: Documents ---
    with doc_sub1:
        # Persist loaded documents in session state so child buttons work across reruns
        if "mcp_docs_list" not in st.session_state:
            st.session_state.mcp_docs_list = None
        if "mcp_docs_meta" not in st.session_state:
            st.session_state.mcp_docs_meta = {}

        if st.button("🔄 Load Documents", use_container_width=True, key="btn_load_docs"):
            with st.spinner("Loading..."):
                result = mcp_list_documents()
            if result.get("success"):
                st.session_state.mcp_docs_list = result
            else:
                st.session_state.mcp_docs_list = None
                st.error(f"❌ {result.get('error', 'Failed to load documents')}")

        # Render document list from session state (survives child-button reruns)
        if st.session_state.mcp_docs_list and st.session_state.mcp_docs_list.get("success"):
            result = st.session_state.mcp_docs_list
            docs = result.get("documents", [])
            st.info(f"**{result.get('total', len(docs))}** documents — **{result.get('total_chunks',0)}** total chunks")

            for doc in docs:
                did = doc.get("document_id", doc.get("id", "?"))
                dname = doc.get("document_name", doc.get("name", "Untitled"))
                doc_status = doc.get("status", "unknown")
                chunks_count = doc.get("chunks_created", doc.get("chunks", "?"))
                lang = doc.get("language", "?")
                status_icon = "🟢" if doc_status in ("processed", "success") else "🟡" if doc_status == "processing" else "⚪"

                with st.expander(f"{status_icon} **{dname}** — {chunks_count} chunks — {lang}", expanded=False):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.code(did, language=None)
                        st.caption(f"Status: {doc_status} | Language: {lang} | Chunks: {chunks_count}")
                        if st.button(f"📋 Details", key=f"det_{did}"):
                            detail = mcp_get_document(did)
                            if detail.get("success"):
                                st.json(detail.get("document", detail))
                            else:
                                st.error(detail.get("error", "Failed"))

                    with c2:
                        st.markdown("**Update Metadata**")
                        new_name = st.text_input("Name", value=dname, key=f"name_{did}")
                        status_options = ["processed", "archived", "pending"]
                        current_status_idx = 0
                        if doc_status == "archived":
                            current_status_idx = 1
                        elif doc_status == "pending":
                            current_status_idx = 2
                        new_status = st.selectbox("Status", status_options,
                                                  index=current_status_idx, key=f"stat_{did}")
                        if st.button("💾 Update", key=f"upd_{did}"):
                            updates = {}
                            if new_name != dname: updates["document_name"] = new_name
                            normalized_old = "processed" if doc_status == "success" else doc_status
                            if new_status != normalized_old: updates["status"] = new_status
                            if updates:
                                r = mcp_update_document(did, updates)
                                if r.get("success"):
                                    st.success("Updated!")
                                    _log_history("ingestion", {"action": "update", "id": did[:12], **updates})
                                    st.session_state.mcp_docs_list = mcp_list_documents()
                                    st.rerun()
                                else:
                                    st.error(r.get("error", "Failed"))
                            else:
                                st.info("No changes")

                        st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
                        confirm_key = f"confirm_del_doc_{did}"
                        if confirm_key not in st.session_state.confirm_delete:
                            st.session_state.confirm_delete[confirm_key] = False
                        if not st.session_state.confirm_delete[confirm_key]:
                            if st.button("🗑️ Delete", key=f"del_{did}", type="secondary"):
                                st.session_state.confirm_delete[confirm_key] = True
                                st.rerun()
                        else:
                            st.warning(f"⚠️ Are you sure you want to delete **{dname}**? This cannot be undone.")
                            dc1, dc2 = st.columns(2)
                            with dc1:
                                if st.button("✅ Yes, Delete", key=f"cdel_y_{did}", type="primary"):
                                    r = mcp_delete_document(did)
                                    if r.get("success"):
                                        st.success(f"Deleted: {dname}")
                                        _log_history("ingestion", {"action": "delete", "id": did[:12], "name": dname})
                                        st.session_state.confirm_delete[confirm_key] = False
                                        st.session_state.mcp_docs_list = mcp_list_documents()
                                        st.rerun()
                                    else:
                                        st.error(r.get("error", "Failed"))
                            with dc2:
                                if st.button("❌ Cancel", key=f"cdel_n_{did}"):
                                    st.session_state.confirm_delete[confirm_key] = False
                                    st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

    # --- Sub-tab: Chunks ---
    with doc_sub2:
        # Auto-populate index dropdown from loaded indexes
        if "mcp_index_names" not in st.session_state:
            st.session_state.mcp_index_names = []

        if st.button("🔄 Refresh Indexes", key="btn_refresh_idx_chunks", use_container_width=True):
            with st.spinner("Loading indexes..."):
                idx_result = mcp_list_indexes()
            if idx_result.get("success"):
                names = [ix.get("index_name", ix.get("index", ix.get("name", "")))
                         for ix in idx_result.get("indexes", []) if isinstance(ix, dict)]
                st.session_state.mcp_index_names = sorted(names) if names else []
            else:
                st.warning("Could not load indexes. You can type an index name below.")

        index_options = st.session_state.mcp_index_names
        if index_options:
            idx_name = st.selectbox("Select Index", options=[""] + index_options,
                                    format_func=lambda x: "(choose an index)" if x == "" else x,
                                    key="chunk_idx_select")
        else:
            idx_name = st.text_input("Index Name", placeholder="aris-doc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                                     key="chunk_idx")

        if idx_name:
            chunk_action = st.radio("Action", ["List Chunks", "Get Chunk", "Create Chunk", "Update Chunk", "Delete Chunk"],
                                    horizontal=True, key="chunk_action")

            if chunk_action == "List Chunks":
                c1, c2, c3 = st.columns(3)
                with c1: offset = st.number_input("Offset", value=0, min_value=0, key="ch_off")
                with c2: limit_val = st.number_input("Limit", value=20, min_value=1, max_value=100, key="ch_lim")
                with c3: src_filter = st.text_input("Source filter", key="ch_src")

                if st.button("📋 List Chunks", use_container_width=True, key="btn_list_chunks"):
                    with st.spinner("Loading..."):
                        result = mcp_list_chunks(idx_name, offset=offset, limit=limit_val,
                                                 source=src_filter if src_filter else None)
                    if result.get("success"):
                        ch_list = result.get("chunks", [])
                        st.info(f"**{result.get('total', len(ch_list))}** total chunks (showing {len(ch_list)})")
                        for i, ch in enumerate(ch_list):
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
                            _log_history("ingestion", {"action": "create_chunk", "index": idx_name, "text": ch_text[:50]})
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
                            _log_history("ingestion", {"action": "update_chunk", "chunk_id": cid[:20], **body})
                        else:
                            st.error(result.get("error", "Failed"))
                    else:
                        st.info("No changes provided")

            elif chunk_action == "Delete Chunk":
                cid = st.text_input("Chunk ID to delete", key="ch_del_id")
                st.markdown('<div class="danger-zone">', unsafe_allow_html=True)
                ck = f"confirm_del_chunk_{cid}" if cid else ""
                if cid and ck not in st.session_state.confirm_delete:
                    st.session_state.confirm_delete[ck] = False
                if cid and not st.session_state.confirm_delete.get(ck, False):
                    if st.button("🗑️ Delete Chunk", type="secondary", use_container_width=True, key="btn_del_chunk"):
                        st.session_state.confirm_delete[ck] = True
                        st.rerun()
                elif cid and st.session_state.confirm_delete.get(ck, False):
                    st.warning(f"⚠️ Are you sure you want to delete chunk `{cid[:20]}...`?")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        if st.button("✅ Yes, Delete", key="cdel_y_chunk", type="primary"):
                            result = mcp_delete_chunk(idx_name, cid)
                            if result.get("success"):
                                st.success(f"✅ Deleted chunk `{cid[:20]}...`")
                                _log_history("ingestion", {"action": "delete_chunk", "index": idx_name, "chunk_id": cid[:20]})
                                st.session_state.confirm_delete[ck] = False
                            else:
                                st.error(result.get("error", "Failed"))
                    with dc2:
                        if st.button("❌ Cancel", key="cdel_n_chunk"):
                            st.session_state.confirm_delete[ck] = False
                            st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Enter an index name above to manage its chunks.")

    # --- Sub-tab: Indexes ---
    with doc_sub3:
        if st.button("🔄 Load Indexes", use_container_width=True, key="btn_load_idx"):
            with st.spinner("Loading..."):
                result = mcp_list_indexes()
            if result.get("success"):
                indexes_list = result.get("indexes", [])
                st.info(f"**{result.get('total', len(indexes_list))}** indexes found")

                aris_indexes = [ix for ix in indexes_list if isinstance(ix, dict) and "aris-doc" in str(ix.get("index",""))]
                other_indexes = [ix for ix in indexes_list if isinstance(ix, dict) and "aris-doc" not in str(ix.get("index",""))]

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
                                ick = f"confirm_del_ix_{name}"
                                if ick not in st.session_state.confirm_delete:
                                    st.session_state.confirm_delete[ick] = False
                                if not st.session_state.confirm_delete[ick]:
                                    if st.button("🗑️ Delete Index", key=f"ixdel_{name}", type="secondary"):
                                        st.session_state.confirm_delete[ick] = True
                                        st.rerun()
                                else:
                                    st.warning(f"⚠️ Delete index **{name}** and ALL its chunks? This cannot be undone.")
                                    dc1, dc2 = st.columns(2)
                                    with dc1:
                                        if st.button("✅ Yes, Delete", key=f"cixdel_y_{name}", type="primary"):
                                            r = mcp_delete_index(name)
                                            if r.get("success"):
                                                st.success(f"Deleted: {name}")
                                                _log_history("ingestion", {"action": "delete_index", "index": name})
                                                st.session_state.confirm_delete[ick] = False
                                                st.rerun()
                                            else:
                                                st.error(r.get("error", "Failed"))
                                    with dc2:
                                        if st.button("❌ Cancel", key=f"cixdel_n_{name}"):
                                            st.session_state.confirm_delete[ick] = False
                                            st.rerun()
                                st.markdown('</div>', unsafe_allow_html=True)

                if other_indexes:
                    with st.expander(f"⚙️ System Indexes ({len(other_indexes)})"):
                        for ix in other_indexes:
                            name = ix.get("index", ix.get("name", "?"))
                            st.text(f"  {name}")
            else:
                st.error(f"❌ {result.get('error', 'Failed')}")

# ============================================================================
# TAB 4 — SYSTEM & SERVER (consolidated)
# ============================================================================
with tab_system:
    st.markdown("""<div class="tool-card system">
        <h3>📊 System & Server Dashboard</h3>
        <p>System statistics, server health, tools, sync, and connectivity — all in one place.</p>
    </div>""", unsafe_allow_html=True)

    # --- Server status bar ---
    srv_col1, srv_col2 = st.columns([2, 1])
    with srv_col1:
        with st.spinner("Checking MCP Server status..."):
            try:
                t0 = time.time()
                srv_health = check_mcp_server_health()
                ping_ms = (time.time() - t0) * 1000
                srv_online = srv_health is not None and srv_health.get("status") in ("healthy", "ok")
                if srv_online:
                    st.success(f"**MCP SERVER ONLINE** — Ping: {ping_ms:.0f}ms")
                    st.caption(f"Service: {srv_health.get('service', 'mcp')} | "
                               f"Tools: {srv_health.get('total_tools', '?')} | "
                               f"Name: {srv_health.get('server_name', 'ARIS RAG MCP Server')}")
                else:
                    st.error("**MCP SERVER OFFLINE / UNREACHABLE**")
            except Exception as e:
                st.error(f"**Connection Error**: {e}")
                srv_online = False
    with srv_col2:
        if st.button("🔄 Force Sync", help="Trigger immediate synchronization", key="btn_sync"):
            with st.status("Syncing...", expanded=True) as status:
                st.write("Sending sync request...")
                try:
                    sync_result = _post("/sync/force", timeout=15)
                    if isinstance(sync_result, dict) and (sync_result.get("success") or sync_result.get("status") in ("success", "synced")):
                        st.write("Sync accepted!")
                        status.update(label="Sync Completed!", state="complete", expanded=False)
                    else:
                        st.write(f"Error: {sync_result.get('error', 'Unknown')}")
                        status.update(label="Sync Failed", state="error", expanded=True)
                except Exception as e:
                    st.write(f"Exception: {e}")
                    status.update(label="Sync Error", state="error", expanded=True)

    st.divider()

    # --- Sub-tabs inside System & Server ---
    sys_tab1, sys_tab2, sys_tab3, sys_tab4 = st.tabs([
        "📊 Statistics", "🛠️ Tools", "📋 Server Info", "🔌 Connection"
    ])

    # --- Sub-tab: Statistics ---
    with sys_tab1:
        if st.button("📊 Load System Stats", use_container_width=True, key="btn_stats"):
            with st.spinner("Loading stats..."):
                result = mcp_get_stats()
            if result.get("success"):
                stats = result.get("stats", result)

                proc = stats.get("processing", {})
                st.markdown("#### Documents")
                mc = st.columns(4)
                mc[0].metric("Documents", proc.get("total_documents", 0))
                mc[1].metric("Total Chunks", proc.get("total_chunks", 0))
                mc[2].metric("Total Pages", proc.get("total_pages", 0))
                mc[3].metric("Total Images", proc.get("total_images", 0))

                lang_dist = proc.get("language_distribution", {})
                if lang_dist:
                    st.markdown("**Languages:** " + ", ".join(f"{k}: {v}" for k, v in lang_dist.items()))

                queries = stats.get("queries", {})
                st.markdown("#### Queries")
                mc = st.columns(3)
                mc[0].metric("Total Queries", queries.get("total_queries", 0))
                avg_resp = queries.get("avg_response_time", queries.get("average_response_time", 0)) or 0
                mc[1].metric("Avg Response", f"{avg_resp:.2f}s")
                success_rate = queries.get("success_rate", 0) or 0
                mc[2].metric("Success Rate", f"{success_rate * 100:.1f}%" if isinstance(success_rate, float) and success_rate <= 1 else f"{success_rate}%")

                costs = stats.get("costs", {})
                if costs and any(v for v in costs.values() if v):
                    st.markdown("#### Costs")
                    mc = st.columns(3)
                    mc[0].metric("Embedding", f"${costs.get('embedding_cost_usd', 0):.4f}")
                    mc[1].metric("Query", f"${costs.get('query_cost_usd', 0):.4f}")
                    mc[2].metric("Total", f"${costs.get('total_cost_usd', 0):.4f}")

                with st.expander("📋 Full Stats JSON"):
                    st.json(stats)
                _log_history("monitoring", {}, result)
            else:
                st.error(result.get("error", "Failed"))

        if st.button("🏥 Service Health Check", use_container_width=True, key="btn_health"):
            health = check_mcp_server_health()
            if health:
                st.json(health)
            else:
                st.error("MCP server unreachable")

    # --- Sub-tab: Tools ---
    with sys_tab2:
        st.subheader("Available MCP Tools")
        if st.button("Load Tools", use_container_width=True, key="btn_srv_tools"):
            with st.spinner("Loading tools..."):
                tools_resp = _get("/tools")
            tools = []
            if isinstance(tools_resp, dict):
                tools = tools_resp.get("tools", [])
            elif isinstance(tools_resp, list):
                tools = tools_resp

            if tools:
                st.info(f"Found **{len(tools)}** MCP tools ready for AI agents.")
                for i, tool in enumerate(tools):
                    tool_name = tool.get("name", "Unknown")
                    tool_desc = tool.get("description", "No description.")
                    with st.expander(f"🔧 **{tool_name}**", expanded=(i == 0)):
                        st.markdown(f"**Description:** {tool_desc}")
                        schema = tool.get("inputSchema", tool.get("input_schema", {}))
                        if schema:
                            st.markdown("**Input Schema:**")
                            st.json(schema)
            else:
                st.warning("No tools returned. Check server configuration.")
                st.json(tools_resp)

    # --- Sub-tab: Server Info ---
    with sys_tab3:
        st.subheader("Server Info")
        if st.button("Load Server Info", use_container_width=True, key="btn_srv_info"):
            with st.spinner("Loading..."):
                info_resp = _get("/info")
            if isinstance(info_resp, dict) and info_resp.get("service"):
                mc = st.columns(3)
                mc[0].metric("Version", info_resp.get("version", "?"))
                mc[1].metric("Tools", info_resp.get("total_tools", "?"))
                mc[2].metric("Service", info_resp.get("service", "?"))

                cats = info_resp.get("tool_categories", {})
                if cats:
                    st.markdown("#### Tool Categories")
                    for cat, desc in cats.items():
                        st.write(f"**{cat}**: {desc}")

                config = info_resp.get("configuration", {})
                if config:
                    st.markdown("#### Configuration")
                    badges = ""
                    for key, val in config.items():
                        color = "rgba(16,185,129,.15)" if val is True or (isinstance(val, (int, float)) and val > 0) else "rgba(255,255,255,.06)"
                        badges += f'<span class="feature-badge" style="background:{color};">{key.replace("_"," ").title()}: {val}</span>'
                    st.markdown(badges, unsafe_allow_html=True)

                with st.expander("Full /info JSON"):
                    st.json(info_resp)
            else:
                st.warning("Could not load server info.")
                st.json(info_resp)

    # --- Sub-tab: Connection ---
    with sys_tab4:
        st.subheader("Connection Details")
        st.code(f"""# MCP Server URL
MCP_SERVER_URL: {MCP_SERVER_URL}

# Architecture Flow
Browser -> Streamlit UI -> HTTP Client -> MCP Service (port 8503)
         -> Gateway (port 8500) -> Ingestion / Retrieval / OpenSearch
        """, language="bash")

        st.markdown("### Troubleshooting")
        st.info("""
If the server shows **OFFLINE**:
1. Check if the MCP container is running: `docker ps | grep aris-mcp`
2. Check container logs: `docker logs aris-mcp`
3. Ensure Docker network `aris-network` connects UI and MCP containers.
4. Verify `MCP_SERVICE_URL` is set correctly in `docker-compose.yml`.
        """)

# ============================================================================
# TAB 5 — HISTORY
# ============================================================================
with tab_history:
    st.markdown("### 📜 Execution History")
    st.caption("History is persisted to disk and survives page reloads.")
    if st.session_state.mcp_history:
        if st.button("🗑️ Clear History", key="btn_clear_hist"):
            st.session_state.mcp_history = []
            _save_persistent_history([])
            st.rerun()

        icons = {"retrieval":"🔍", "ingestion":"📄", "monitoring":"📊"}

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
    <p>🔌 MCP Client v5.0 for ARIS RAG System — 3 tools · 5 tabs</p>
    <p>Server: <code>{MCP_SERVER_URL}</code></p>
</div>
""", unsafe_allow_html=True)
