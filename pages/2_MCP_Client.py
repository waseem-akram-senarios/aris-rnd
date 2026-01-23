"""
MCP Client - Test Interface for ARIS RAG MCP Server

This page provides a direct testing interface for the MCP server tools:
- rag_ingest: Add documents to the RAG system
- rag_search: Query documents with advanced search

You can test both tools directly without needing Claude Desktop.
"""

import streamlit as st
import sys
import os
import json
import time
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

# Custom CSS for better styling
st.markdown("""
<style>
    .mcp-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .tool-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin-bottom: 1rem;
    }
    .result-card {
        background: #e8f5e9;
        padding: 1rem;
        border-radius: 8px;
        margin-top: 1rem;
    }
    .error-card {
        background: #ffebee;
        padding: 1rem;
        border-radius: 8px;
        margin-top: 1rem;
    }
    .confidence-high { color: #2e7d32; font-weight: bold; }
    .confidence-medium { color: #f57c00; font-weight: bold; }
    .confidence-low { color: #c62828; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'mcp_results' not in st.session_state:
    st.session_state.mcp_results = []
if 'mcp_history' not in st.session_state:
    st.session_state.mcp_history = []

# Get MCP server URL
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8503")
if os.getenv("SERVICE_TYPE") == "ui":
    # Running in Docker, use internal service name
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


def format_confidence(confidence):
    """Format confidence score with color coding."""
    if confidence >= 70:
        return f'<span class="confidence-high">{confidence:.1f}%</span>'
    elif confidence >= 40:
        return f'<span class="confidence-medium">{confidence:.1f}%</span>'
    else:
        return f'<span class="confidence-low">{confidence:.1f}%</span>'


# Header
st.markdown("""
<div class="mcp-header">
    <h1>🔌 MCP Client - Direct Tool Testing</h1>
    <p>Test the ARIS RAG MCP server tools directly from your browser</p>
</div>
""", unsafe_allow_html=True)

# Server Status
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    st.markdown("### 📡 Server Status")
    health = check_mcp_server_health()
    if health:
        st.success(f"✅ MCP Server: **{health.get('status', 'unknown').upper()}**")
        st.caption(f"Server: {health.get('server_name', 'N/A')}")
    else:
        st.warning("⚠️ MCP Server not reachable via HTTP. Using direct engine calls.")

with col2:
    st.markdown("### 🔧 Available Tools")
    st.info("**rag_ingest** • **rag_search**")

with col3:
    st.markdown("### ⚙️ Features")
    st.caption("✅ Hybrid Search")
    st.caption("✅ Reranking")
    st.caption("✅ Agentic RAG")

st.divider()

# Main content - Two columns for the two tools
tool_tab1, tool_tab2, history_tab = st.tabs(["📥 rag_ingest", "🔍 rag_search", "📜 History"])

# ============================================================================
# TAB 1: rag_ingest
# ============================================================================
with tool_tab1:
    st.markdown("### 📥 rag_ingest - Add Documents to RAG System")
    st.markdown("""
    <div class="tool-card">
    <strong>Purpose:</strong> Ingest content into the RAG vector database<br>
    <strong>Supports:</strong> Plain text, S3 URIs (PDF, DOCX, DOC, TXT, MD, HTML)
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Content input
        content_type = st.radio(
            "Content Type",
            ["Plain Text", "S3 URI"],
            horizontal=True,
            key="ingest_content_type"
        )
        
        if content_type == "Plain Text":
            content = st.text_area(
                "Content to Ingest",
                height=200,
                placeholder="Enter the text content you want to add to the RAG system...\n\nExample:\nThis is a technical document about machine maintenance procedures. Regular maintenance includes checking oil levels, inspecting belts, and cleaning filters.",
                key="ingest_content"
            )
        else:
            content = st.text_input(
                "S3 URI",
                placeholder="s3://bucket-name/path/to/document.pdf",
                key="ingest_s3_uri"
            )
            st.caption("Supported formats: PDF, DOCX, DOC, TXT, MD, HTML")
    
    with col2:
        st.markdown("#### Metadata (Optional)")
        
        # Common metadata fields
        domain = st.selectbox(
            "Domain",
            ["", "ticket", "machine_manual", "policy", "troubleshooting", "other"],
            key="ingest_domain"
        )
        
        language = st.selectbox(
            "Language",
            ["en", "es", "de", "fr", "it", "pt", "ru", "ja", "ko", "zh", "ar"],
            key="ingest_language"
        )
        
        source = st.text_input(
            "Source Identifier",
            placeholder="e.g., manual_v2.pdf",
            key="ingest_source"
        )
        
        # Custom metadata
        custom_metadata = st.text_area(
            "Custom Metadata (JSON)",
            placeholder='{"department": "engineering", "version": "2.0"}',
            height=80,
            key="ingest_custom_metadata"
        )
    
    # Ingest button
    if st.button("📥 Ingest Document", type="primary", key="btn_ingest"):
        if not content:
            st.error("Please enter content to ingest")
        else:
            # Build metadata
            metadata = {}
            if domain:
                metadata["domain"] = domain
            if language:
                metadata["language"] = language
            if source:
                metadata["source"] = source
            
            # Parse custom metadata
            if custom_metadata:
                try:
                    custom = json.loads(custom_metadata)
                    metadata.update(custom)
                except json.JSONDecodeError:
                    st.error("Invalid JSON in custom metadata")
                    st.stop()
            
            # Execute ingestion
            with st.spinner("Ingesting document..."):
                try:
                    engine = get_mcp_engine()
                    if engine:
                        start_time = time.time()
                        result = engine.ingest(content, metadata if metadata else None)
                        elapsed = time.time() - start_time
                        
                        if result.get("success"):
                            st.success("✅ Document ingested successfully!")
                            
                            # Display results
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.metric("Document ID", result.get("document_id", "N/A")[:20] + "...")
                            with col_b:
                                st.metric("Chunks Created", result.get("chunks_created", 0))
                            with col_c:
                                st.metric("Time", f"{elapsed:.2f}s")
                            
                            # Show metadata
                            with st.expander("📋 Full Response", expanded=False):
                                st.json(result)
                            
                            # Add to history
                            st.session_state.mcp_history.append({
                                "tool": "rag_ingest",
                                "timestamp": datetime.now().isoformat(),
                                "input": {"content": content[:100] + "...", "metadata": metadata},
                                "result": result,
                                "elapsed": elapsed
                            })
                        else:
                            st.error(f"❌ Ingestion failed: {result.get('message', 'Unknown error')}")
                    else:
                        st.error("Failed to initialize MCP Engine")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# ============================================================================
# TAB 2: rag_search
# ============================================================================
with tool_tab2:
    st.markdown("### 🔍 rag_search - Query Documents")
    st.markdown("""
    <div class="tool-card">
    <strong>Purpose:</strong> Search the RAG system with advanced accuracy features<br>
    <strong>Features:</strong> Hybrid search, FlashRank reranking, Agentic RAG, Confidence scores
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Query input
        query = st.text_area(
            "Search Query",
            height=100,
            placeholder="Enter your question or search query...\n\nExample: What are the maintenance procedures for the hydraulic system?",
            key="search_query"
        )
        
        # Quick query examples
        st.caption("**Quick Examples:**")
        example_cols = st.columns(3)
        with example_cols[0]:
            if st.button("📋 Maintenance", key="ex1"):
                st.session_state.search_query = "What are the maintenance procedures?"
                st.rerun()
        with example_cols[1]:
            if st.button("🔧 Troubleshooting", key="ex2"):
                st.session_state.search_query = "How do I troubleshoot common errors?"
                st.rerun()
        with example_cols[2]:
            if st.button("📖 Overview", key="ex3"):
                st.session_state.search_query = "Give me an overview of the system"
                st.rerun()
    
    with col2:
        st.markdown("#### Search Options")
        
        # Number of results
        k = st.slider("Results (k)", 1, 20, 5, key="search_k")
        
        # Search mode
        search_mode = st.selectbox(
            "Search Mode",
            ["hybrid", "semantic", "keyword"],
            index=0,
            key="search_mode"
        )
        st.caption("hybrid = semantic + keyword (recommended)")
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            use_agentic_rag = st.checkbox("Enable Agentic RAG", value=True, key="search_agentic")
            st.caption("Decomposes complex queries into sub-queries")
            
            include_answer = st.checkbox("Generate LLM Answer", value=True, key="search_answer")
            st.caption("Generate a synthesized answer (slower but more useful)")
        
        # Filters
        st.markdown("#### Filters (Optional)")
        filter_domain = st.selectbox(
            "Filter by Domain",
            ["", "ticket", "machine_manual", "policy", "troubleshooting"],
            key="search_filter_domain"
        )
        filter_language = st.selectbox(
            "Filter by Language",
            ["", "en", "es", "de", "fr"],
            key="search_filter_language"
        )
        filter_source = st.text_input(
            "Filter by Source",
            placeholder="document_name.pdf",
            key="search_filter_source"
        )
    
    # Search button
    if st.button("🔍 Search", type="primary", key="btn_search"):
        if not query:
            st.error("Please enter a search query")
        else:
            # Build filters
            filters = {}
            if filter_domain:
                filters["domain"] = filter_domain
            if filter_language:
                filters["language"] = filter_language
            if filter_source:
                filters["source"] = filter_source
            
            # Execute search
            with st.spinner("Searching..." + (" (with Agentic RAG)" if use_agentic_rag else "")):
                try:
                    engine = get_mcp_engine()
                    if engine:
                        start_time = time.time()
                        result = engine.search(
                            query=query,
                            filters=filters if filters else None,
                            k=k,
                            search_mode=search_mode,
                            use_agentic_rag=use_agentic_rag,
                            include_answer=include_answer
                        )
                        elapsed = time.time() - start_time
                        
                        if result.get("success"):
                            # Display metrics
                            col_a, col_b, col_c, col_d = st.columns(4)
                            with col_a:
                                st.metric("Results", result.get("total_results", 0))
                            with col_b:
                                st.metric("Search Mode", result.get("search_mode", "N/A"))
                            with col_c:
                                accuracy_info = result.get("accuracy_info", {})
                                sub_queries = accuracy_info.get("sub_queries_generated", 0)
                                st.metric("Sub-queries", sub_queries if use_agentic_rag else "N/A")
                            with col_d:
                                st.metric("Time", f"{elapsed:.2f}s")
                            
                            # Display answer if available
                            if include_answer and result.get("answer"):
                                st.markdown("### 💡 Answer")
                                st.info(result.get("answer"))
                            
                            # Display results
                            st.markdown("### 📄 Retrieved Chunks")
                            
                            results = result.get("results", [])
                            if results:
                                for i, chunk in enumerate(results):
                                    confidence = chunk.get("confidence", 0)
                                    source = chunk.get("source", "Unknown")
                                    page = chunk.get("page", "N/A")
                                    content_preview = chunk.get("snippet", chunk.get("content", ""))[:300]
                                    
                                    # Confidence color
                                    if confidence >= 70:
                                        conf_color = "🟢"
                                    elif confidence >= 40:
                                        conf_color = "🟡"
                                    else:
                                        conf_color = "🔴"
                                    
                                    with st.expander(f"{conf_color} **Result {i+1}** - {source} (Page {page}) - Confidence: {confidence:.1f}%", expanded=(i < 3)):
                                        st.markdown(f"**Content:**\n{content_preview}...")
                                        
                                        # Metadata
                                        metadata = chunk.get("metadata", {})
                                        if metadata:
                                            st.markdown("**Metadata:**")
                                            st.json(metadata)
                            else:
                                st.warning("No results found. Try a different query or remove filters.")
                            
                            # Accuracy info
                            with st.expander("📊 Accuracy Info", expanded=False):
                                st.json(result.get("accuracy_info", {}))
                            
                            # Add to history
                            st.session_state.mcp_history.append({
                                "tool": "rag_search",
                                "timestamp": datetime.now().isoformat(),
                                "input": {"query": query, "filters": filters, "k": k, "search_mode": search_mode},
                                "result_count": result.get("total_results", 0),
                                "elapsed": elapsed
                            })
                        else:
                            st.error(f"❌ Search failed: {result.get('message', 'Unknown error')}")
                    else:
                        st.error("Failed to initialize MCP Engine")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

# ============================================================================
# TAB 3: History
# ============================================================================
with history_tab:
    st.markdown("### 📜 Tool Execution History")
    
    if st.session_state.mcp_history:
        # Clear history button
        if st.button("🗑️ Clear History"):
            st.session_state.mcp_history = []
            st.rerun()
        
        # Display history in reverse order (newest first)
        for i, entry in enumerate(reversed(st.session_state.mcp_history)):
            tool_icon = "📥" if entry["tool"] == "rag_ingest" else "🔍"
            with st.expander(f"{tool_icon} **{entry['tool']}** - {entry['timestamp']}", expanded=(i < 2)):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Input:**")
                    st.json(entry.get("input", {}))
                with col2:
                    st.markdown("**Result:**")
                    if entry["tool"] == "rag_ingest":
                        result = entry.get("result", {})
                        st.write(f"✅ Success: {result.get('success', False)}")
                        st.write(f"📄 Chunks: {result.get('chunks_created', 'N/A')}")
                    else:
                        st.write(f"📊 Results: {entry.get('result_count', 0)}")
                    st.write(f"⏱️ Time: {entry.get('elapsed', 0):.2f}s")
    else:
        st.info("No tool executions yet. Use the tabs above to test the MCP tools.")

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    <p>🔌 MCP Client for ARIS RAG System</p>
    <p>Server: <code>{}</code> | Tools: <code>rag_ingest</code>, <code>rag_search</code></p>
</div>
""".format(MCP_SERVER_URL), unsafe_allow_html=True)

