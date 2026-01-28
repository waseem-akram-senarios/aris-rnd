"""
MCP Client - Test Interface for ARIS RAG MCP Server
Premium Glassmorphism Design matching the main app

Tools:
- rag_ingest / rag_upload_document: Add documents to the RAG system
- rag_search: Query documents with advanced search
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
    /* MCP Header */
    .mcp-header {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-radius: 16px;
        padding: 2.5rem;
        margin-bottom: 2rem;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    
    .mcp-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: radial-gradient(circle at 30% 50%, rgba(16, 185, 129, 0.15) 0%, transparent 50%),
                    radial-gradient(circle at 70% 50%, rgba(59, 130, 246, 0.15) 0%, transparent 50%);
        pointer-events: none;
    }
    
    .mcp-header h1 {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #34d399 0%, #60a5fa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        position: relative;
    }
    
    .mcp-header p {
        color: #94a3b8;
        font-size: 1.1rem;
        position: relative;
    }
    
    /* Status Cards */
    .status-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .status-card {
        flex: 1;
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.25rem;
        backdrop-filter: blur(10px);
    }
    
    .status-card.connected {
        border-color: rgba(16, 185, 129, 0.4);
    }
    
    .status-card h4 {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    
    .status-card .value {
        font-size: 1rem;
        font-weight: 600;
        color: #f1f5f9;
    }
    
    .status-card .value.success {
        color: #34d399;
    }
    
    /* Tool Card */
    .tool-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        border-left: 4px solid #3b82f6;
    }
    
    .tool-card.ingest {
        border-left-color: #10b981;
    }
    
    .tool-card.search {
        border-left-color: #8b5cf6;
    }
    
    .tool-card h3 {
        color: #f1f5f9;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }
    
    .tool-card p {
        color: #94a3b8;
        font-size: 0.9rem;
    }
    
    /* Result Cards */
    .result-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s ease;
    }
    
    .result-card:hover {
        border-color: rgba(59, 130, 246, 0.3);
        transform: translateX(4px);
    }
    
    .result-card .result-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
    }
    
    .result-card .result-source {
        color: #60a5fa;
        font-weight: 500;
    }
    
    .result-card .result-confidence {
        font-size: 0.85rem;
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
    }
    
    .confidence-high {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
    }
    
    .confidence-medium {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
    }
    
    .confidence-low {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
    }
    
    /* Answer Box */
    .answer-box {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    
    .answer-box h4 {
        color: #60a5fa;
        font-size: 1rem;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .answer-box .answer-text {
        color: #e2e8f0;
        line-height: 1.7;
    }
    
    /* Metrics Row */
    .metrics-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .metric-card {
        flex: 1;
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    
    .metric-card .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-card .metric-label {
        color: #94a3b8;
        font-size: 0.8rem;
        margin-top: 0.25rem;
    }
    
    /* Feature Badge */
    .feature-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.65rem;
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 999px;
        font-size: 0.75rem;
        color: #60a5fa;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    /* Quick Action Button */
    .quick-btn {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 0.5rem 1rem;
        color: #94a3b8;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .quick-btn:hover {
        background: rgba(59, 130, 246, 0.1);
        border-color: rgba(59, 130, 246, 0.3);
        color: #60a5fa;
    }
    
    /* History Item */
    .history-item {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .history-item .history-tool {
        color: #60a5fa;
        font-weight: 500;
    }
    
    .history-item .history-time {
        color: #64748b;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'mcp_results' not in st.session_state:
    st.session_state.mcp_results = []
if 'mcp_history' not in st.session_state:
    st.session_state.mcp_history = []
if 'pending_search_query' not in st.session_state:
    st.session_state.pending_search_query = None

# Get MCP server URL
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8503")
if os.getenv("SERVICE_TYPE") == "ui":
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp:8503")


def get_mcp_engine():
    """Get the MCP Engine for direct tool execution."""
    try:
        from services.mcp.engine import MCPEngine
        return MCPEngine()
    except Exception as e:
        st.error(f"Failed to initialize MCP Engine: {e}")
        return None


def check_mcp_server_health():
    """Check if the MCP server is healthy."""
    try:
        response = requests.get(f"{MCP_SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def get_confidence_class(confidence):
    """Get CSS class for confidence level."""
    if confidence >= 70:
        return "confidence-high"
    elif confidence >= 40:
        return "confidence-medium"
    return "confidence-low"


# ============================================================================
# MAIN UI
# ============================================================================

# Header
st.markdown("""
<div class="mcp-header">
    <h1>🔌 MCP Client</h1>
    <p>Direct testing interface for ARIS RAG MCP Server tools</p>
</div>
""", unsafe_allow_html=True)

# Status Row
col1, col2, col3 = st.columns(3)

with col1:
    health = check_mcp_server_health()
    if health:
        st.markdown("""
        <div class="status-card connected">
            <h4>📡 Server Status</h4>
            <div class="value success">✓ Connected</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="status-card">
            <h4>📡 Server Status</h4>
            <div class="value">Using Direct Engine</div>
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="status-card">
        <h4>🔧 Available Tools</h4>
        <div class="value">rag_ingest • rag_search</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="status-card">
        <h4>✨ Features</h4>
        <div>
            <span class="feature-badge">Hybrid Search</span>
            <span class="feature-badge">Reranking</span>
            <span class="feature-badge">Agentic RAG</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Main Tabs
tab_ingest, tab_search, tab_history = st.tabs(["📥 Add Documents", "🔍 Search", "📜 History"])

# ============================================================================
# TAB 1: Add Documents
# ============================================================================
with tab_ingest:
    st.markdown("""
    <div class="tool-card ingest">
        <h3>📥 Add Documents to RAG System</h3>
        <p>Ingest content into the vector database. Supports plain text, S3 URIs, or direct file upload.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        content_type = st.radio(
            "Content Type",
            ["Plain Text", "S3 URI", "Upload File"],
            horizontal=True,
            key="ingest_type"
        )
        
        content = None
        uploaded_file = None
        
        if content_type == "Plain Text":
            content = st.text_area(
                "Content",
                height=200,
                placeholder="Enter text content to add to the RAG system...",
                key="ingest_content"
            )
        elif content_type == "S3 URI":
            content = st.text_input(
                "S3 URI",
                placeholder="s3://bucket-name/path/to/document.pdf",
                key="ingest_s3"
            )
            st.caption("Supported: PDF, DOCX, DOC, TXT, MD, HTML")
        else:
            uploaded_file = st.file_uploader(
                "Upload Document",
                type=["pdf", "docx", "doc", "txt", "md", "html"],
                key="upload_file"
            )
            if uploaded_file:
                st.success(f"✅ Selected: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
    
    with col2:
        st.markdown("#### Metadata")
        
        domain = st.selectbox("Domain", ["", "ticket", "machine_manual", "policy", "troubleshooting", "other"])
        language = st.selectbox("Language", ["en", "es", "de", "fr", "it", "pt", "ru", "ja", "ko", "zh", "ar"])
        source = st.text_input("Source ID", placeholder="e.g., manual_v2.pdf")
        
        custom_meta = st.text_area("Custom JSON", placeholder='{"version": "2.0"}', height=80)
    
    if st.button("📥 Ingest Document", type="primary", use_container_width=True):
        has_content = uploaded_file if content_type == "Upload File" else (content and content.strip())
        
        if not has_content:
            st.error("Please provide content to ingest")
        else:
            metadata = {}
            if domain: metadata["domain"] = domain
            if language: metadata["language"] = language
            if source: metadata["source"] = source
            if custom_meta:
                try:
                    metadata.update(json.loads(custom_meta))
                except:
                    st.error("Invalid JSON in custom metadata")
                    st.stop()
            
            if content_type == "Upload File":
                with st.spinner(f"Processing {uploaded_file.name}..."):
                    try:
                        engine = get_mcp_engine()
                        if engine:
                            start_time = time.time()
                            file_bytes = uploaded_file.read()
                            ext = uploaded_file.name.lower().split(".")[-1]
                            
                            if ext in ["pdf", "docx", "doc"]:
                                file_content = base64.b64encode(file_bytes).decode("utf-8")
                            else:
                                try:
                                    file_content = file_bytes.decode("utf-8")
                                except:
                                    file_content = base64.b64encode(file_bytes).decode("utf-8")
                            
                            result = engine.upload_document(file_content, uploaded_file.name, metadata or None)
                            elapsed = time.time() - start_time
                            
                            if result.get("success"):
                                st.success("✅ Document uploaded successfully!")
                                
                                col_a, col_b, col_c, col_d = st.columns(4)
                                col_a.metric("Document ID", result.get("document_id", "N/A")[:12] + "...")
                                col_b.metric("Chunks", result.get("chunks_created", 0))
                                col_c.metric("Pages", result.get("pages_extracted", "N/A"))
                                col_d.metric("Time", f"{elapsed:.1f}s")
                                
                                with st.expander("📋 Full Response"):
                                    st.json(result)
                                
                                st.session_state.mcp_history.append({
                                    "tool": "rag_upload_document",
                                    "timestamp": datetime.now().isoformat(),
                                    "input": {"filename": uploaded_file.name},
                                    "result": result,
                                    "elapsed": elapsed
                                })
                            else:
                                st.error(f"❌ Upload failed: {result.get('message', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            else:
                with st.spinner("Ingesting..."):
                    try:
                        engine = get_mcp_engine()
                        if engine:
                            start_time = time.time()
                            result = engine.ingest(content, metadata or None)
                            elapsed = time.time() - start_time
                            
                            if result.get("success"):
                                st.success("✅ Document ingested!")
                                col_a, col_b, col_c = st.columns(3)
                                col_a.metric("Document ID", result.get("document_id", "N/A")[:12] + "...")
                                col_b.metric("Chunks", result.get("chunks_created", 0))
                                col_c.metric("Time", f"{elapsed:.1f}s")
                                
                                st.session_state.mcp_history.append({
                                    "tool": "rag_ingest",
                                    "timestamp": datetime.now().isoformat(),
                                    "input": {"content_length": len(content)},
                                    "result": result,
                                    "elapsed": elapsed
                                })
                            else:
                                st.error(f"❌ Failed: {result.get('message', 'Unknown error')}")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

# ============================================================================
# TAB 2: Search
# ============================================================================
with tab_search:
    st.markdown("""
    <div class="tool-card search">
        <h3>🔍 Search Documents</h3>
        <p>Query the RAG system with hybrid search, reranking, and optional Agentic RAG decomposition.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Handle pending query from example buttons
        default_query = st.session_state.pending_search_query or ""
        if st.session_state.pending_search_query:
            st.session_state.pending_search_query = None
        
        query = st.text_area(
            "Search Query",
            value=default_query,
            height=100,
            placeholder="Enter your question...\n\nExample: What are the maintenance procedures for the hydraulic system?",
            key="search_query"
        )
        
        # Quick examples
        st.caption("**Quick Examples:**")
        ex_cols = st.columns(4)
        with ex_cols[0]:
            if st.button("📋 Maintenance", use_container_width=True):
                st.session_state.pending_search_query = "What are the maintenance procedures?"
                st.rerun()
        with ex_cols[1]:
            if st.button("🔧 Troubleshoot", use_container_width=True):
                st.session_state.pending_search_query = "How to troubleshoot common errors?"
                st.rerun()
        with ex_cols[2]:
            if st.button("📖 Overview", use_container_width=True):
                st.session_state.pending_search_query = "Give me an overview of the system"
                st.rerun()
        with ex_cols[3]:
            if st.button("📜 Policy", use_container_width=True):
                st.session_state.pending_search_query = "What is the attendance policy?"
                st.rerun()
    
    with col2:
        st.markdown("#### Options")
        
        k = st.slider("Results (k)", 1, 20, 5)
        search_mode = st.selectbox("Search Mode", ["hybrid", "semantic", "keyword"], index=0)
        st.caption("hybrid = semantic + keyword")
        
        with st.expander("⚙️ Advanced"):
            use_agentic = st.checkbox("Agentic RAG", value=True, help="Decompose complex queries")
            include_answer = st.checkbox("Generate Answer", value=True, help="LLM-synthesized answer")
        
        st.markdown("#### Filters")
        filter_domain = st.selectbox("Domain", ["", "ticket", "machine_manual", "policy", "troubleshooting"])
        filter_source = st.text_input("Source", placeholder="document.pdf")
    
    if st.button("🔍 Search", type="primary", use_container_width=True):
        if not query:
            st.error("Please enter a search query")
        else:
            filters = {}
            if filter_domain: filters["domain"] = filter_domain
            if filter_source: filters["source"] = filter_source
            
            with st.spinner("Searching..." + (" (Agentic RAG)" if use_agentic else "")):
                try:
                    engine = get_mcp_engine()
                    if engine:
                        start_time = time.time()
                        result = engine.search(
                            query=query,
                            filters=filters or None,
                            k=k,
                            search_mode=search_mode,
                            use_agentic_rag=use_agentic,
                            include_answer=include_answer
                        )
                        elapsed = time.time() - start_time
                        
                        if result.get("success"):
                            # Metrics
                            st.markdown(f"""
                            <div class="metrics-row">
                                <div class="metric-card">
                                    <div class="metric-value">{result.get('total_results', 0)}</div>
                                    <div class="metric-label">Results</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{result.get('search_mode', 'N/A')}</div>
                                    <div class="metric-label">Search Mode</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{result.get('accuracy_info', {}).get('sub_queries_generated', 0)}</div>
                                    <div class="metric-label">Sub-queries</div>
                                </div>
                                <div class="metric-card">
                                    <div class="metric-value">{elapsed:.2f}s</div>
                                    <div class="metric-label">Time</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Answer
                            if include_answer and result.get("answer"):
                                st.markdown(f"""
                                <div class="answer-box">
                                    <h4>💡 Answer</h4>
                                    <div class="answer-text">{result.get('answer')}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # Results
                            st.markdown("### 📄 Retrieved Chunks")
                            
                            results = result.get("results", [])
                            if results:
                                for i, chunk in enumerate(results):
                                    confidence = chunk.get("confidence", 0)
                                    source = chunk.get("source", "Unknown")
                                    page = chunk.get("page", "N/A")
                                    snippet = chunk.get("snippet", chunk.get("content", ""))[:300]
                                    conf_class = get_confidence_class(confidence)
                                    
                                    with st.expander(f"{'🟢' if confidence >= 70 else '🟡' if confidence >= 40 else '🔴'} **Result {i+1}** - {source} (Page {page}) - Confidence: {confidence:.1f}%", expanded=(i < 3)):
                                        st.markdown(snippet)
                                        if chunk.get("metadata"):
                                            with st.expander("Metadata"):
                                                st.json(chunk["metadata"])
                            else:
                                st.warning("No results found. Try a different query or remove filters.")
                            
                            with st.expander("📊 Accuracy Info"):
                                st.json(result.get("accuracy_info", {}))
                            
                            st.session_state.mcp_history.append({
                                "tool": "rag_search",
                                "timestamp": datetime.now().isoformat(),
                                "input": {"query": query[:50], "k": k},
                                "result_count": result.get("total_results", 0),
                                "elapsed": elapsed
                            })
                        else:
                            st.error(f"❌ Search failed: {result.get('message', 'Unknown error')}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

# ============================================================================
# TAB 3: History
# ============================================================================
with tab_history:
    st.markdown("### 📜 Execution History")
    
    if st.session_state.mcp_history:
        if st.button("🗑️ Clear History"):
            st.session_state.mcp_history = []
            st.rerun()
        
        for i, entry in enumerate(reversed(st.session_state.mcp_history)):
            icons = {"rag_ingest": "📥", "rag_upload_document": "📤", "rag_search": "🔍"}
            icon = icons.get(entry["tool"], "🔧")
            
            with st.expander(f"{icon} **{entry['tool']}** - {entry['timestamp'][:19]}", expanded=(i < 2)):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Input:**")
                    st.json(entry.get("input", {}))
                with col2:
                    st.markdown("**Result:**")
                    if entry["tool"] in ["rag_ingest", "rag_upload_document"]:
                        result = entry.get("result", {})
                        st.write(f"✅ Success: {result.get('success', False)}")
                        st.write(f"📄 Chunks: {result.get('chunks_created', 'N/A')}")
                    else:
                        st.write(f"📊 Results: {entry.get('result_count', 0)}")
                    st.write(f"⏱️ Time: {entry.get('elapsed', 0):.2f}s")
    else:
        st.info("📭 No executions yet. Use the tabs above to test MCP tools.")

# Footer
st.divider()
st.markdown(f"""
<div style="text-align: center; color: #64748b; font-size: 0.85rem;">
    <p>🔌 MCP Client for ARIS RAG System</p>
    <p>Server: <code>{MCP_SERVER_URL}</code> | Tools: <code>rag_ingest</code>, <code>rag_search</code></p>
</div>
""", unsafe_allow_html=True)
