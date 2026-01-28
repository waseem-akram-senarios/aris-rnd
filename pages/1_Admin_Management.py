"""
ARIS Admin Management - CRUD Operations for Documents and Vector Database
Premium Glassmorphism Design
"""
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any

# Page configuration
st.set_page_config(
    page_title="ARIS Admin - Document & Vector Management",
    page_icon="⚙️",
    layout="wide"
)

# Apply the same CSS as the main app
from api.styles import get_custom_css
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Additional Admin-specific CSS
st.markdown("""
<style>
    /* Admin Header */
    .admin-header {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(59, 130, 246, 0.2) 100%);
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .admin-header h1 {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #a78bfa 0%, #60a5fa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .admin-header p {
        color: #94a3b8;
        font-size: 1.1rem;
    }
    
    /* Stats Cards */
    .stats-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .stat-card {
        flex: 1;
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        backdrop-filter: blur(10px);
    }
    
    .stat-card .stat-value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .stat-card .stat-label {
        color: #94a3b8;
        font-size: 0.85rem;
        margin-top: 0.25rem;
    }
    
    /* Action Cards */
    .action-card {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
    }
    
    .action-card:hover {
        border-color: rgba(59, 130, 246, 0.3);
        transform: translateY(-2px);
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .status-success {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .status-failed {
        background: rgba(239, 68, 68, 0.2);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    .status-processing {
        background: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    
    /* Table Styling */
    .dataframe {
        background: rgba(30, 41, 59, 0.4) !important;
        border-radius: 8px !important;
    }
    
    /* Sidebar Quick Stats */
    .sidebar-stat {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        text-align: center;
    }
    
    .sidebar-stat .value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #60a5fa;
    }
    
    .sidebar-stat .label {
        font-size: 0.75rem;
        color: #94a3b8;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
import os
DEFAULT_GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8500" if os.path.exists("/.dockerenv") else "http://localhost:8500")
DEFAULT_INGESTION_URL = os.getenv("INGESTION_URL", "http://ingestion:8501" if os.path.exists("/.dockerenv") else "http://localhost:8501")
DEFAULT_RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://retrieval:8502" if os.path.exists("/.dockerenv") else "http://localhost:8502")

def get_gateway_url():
    return os.getenv("GATEWAY_URL", DEFAULT_GATEWAY_URL)

def get_ingestion_url():
    return os.getenv("INGESTION_URL", DEFAULT_INGESTION_URL)

def get_retrieval_url():
    return os.getenv("RETRIEVAL_URL", DEFAULT_RETRIEVAL_URL)


# ============================================================================
# API Helper Functions
# ============================================================================

def _get_service_url(endpoint: str) -> str:
    """Determine which service URL to use based on endpoint path."""
    if endpoint == "/admin/documents/registry-stats":
        return get_ingestion_url()
    elif endpoint.startswith("/admin/index") or endpoint.startswith("/admin/search"):
        return get_retrieval_url()
    else:
        return get_gateway_url()

def api_get(endpoint: str, params: dict = None) -> dict:
    """Make GET request to appropriate service."""
    try:
        base_url = _get_service_url(endpoint)
        url = f"{base_url}{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}

def api_post(endpoint: str, data: dict = None, json_data: dict = None) -> dict:
    """Make POST request to appropriate service."""
    try:
        base_url = _get_service_url(endpoint)
        url = f"{base_url}{endpoint}"
        response = requests.post(url, data=data, json=json_data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}

def api_put(endpoint: str, json_data: dict) -> dict:
    """Make PUT request to appropriate service."""
    try:
        base_url = _get_service_url(endpoint)
        url = f"{base_url}{endpoint}"
        response = requests.put(url, json=json_data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}

def api_delete(endpoint: str, params: dict = None) -> dict:
    """Make DELETE request to appropriate service."""
    try:
        base_url = _get_service_url(endpoint)
        url = f"{base_url}{endpoint}"
        response = requests.delete(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


def get_status_badge(status: str) -> str:
    """Generate HTML for status badge."""
    status_lower = status.lower()
    if status_lower == "success":
        return '<span class="status-badge status-success">✓ Success</span>'
    elif status_lower == "failed":
        return '<span class="status-badge status-failed">✗ Failed</span>'
    elif status_lower == "processing":
        return '<span class="status-badge status-processing">⟳ Processing</span>'
    else:
        return f'<span class="status-badge">{status}</span>'


# ============================================================================
# UI Components
# ============================================================================

def render_document_management():
    """Render Document Registry CRUD section."""
    st.markdown("### 📚 Document Registry")
    
    # Get documents from registry
    docs_response = api_get("/documents")
    documents = docs_response.get("documents", [])
    
    # Statistics cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">{}</div>
            <div class="stat-label">Total Documents</div>
        </div>
        """.format(len(documents)), unsafe_allow_html=True)
    with col2:
        success_count = sum(1 for d in documents if d.get("status") == "success")
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">{}</div>
            <div class="stat-label">Processed</div>
        </div>
        """.format(success_count), unsafe_allow_html=True)
    with col3:
        total_chunks = sum(d.get("chunks_created", 0) for d in documents)
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">{}</div>
            <div class="stat-label">Total Chunks</div>
        </div>
        """.format(total_chunks), unsafe_allow_html=True)
    with col4:
        total_images = sum(d.get("images_stored", 0) or d.get("image_count", 0) for d in documents)
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">{}</div>
            <div class="stat-label">Images Stored</div>
        </div>
        """.format(total_images), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Document List
    if documents:
        # Create DataFrame for display
        df_data = []
        for doc in documents:
            df_data.append({
                "ID": doc.get("document_id", "")[:12] + "...",
                "Full ID": doc.get("document_id", ""),
                "Name": doc.get("document_name", ""),
                "Status": doc.get("status", "unknown"),
                "Language": doc.get("language", "eng"),
                "Chunks": doc.get("chunks_created", 0),
                "Images": doc.get("images_stored", 0) or doc.get("image_count", 0),
                "Parser": doc.get("parser_used", "unknown"),
                "Created": doc.get("created_at", "")[:19] if doc.get("created_at") else ""
            })
        
        df = pd.DataFrame(df_data)
        
        # Display table
        st.dataframe(
            df[["ID", "Name", "Status", "Language", "Chunks", "Images", "Parser", "Created"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.TextColumn("Status", help="Document processing status"),
                "Chunks": st.column_config.NumberColumn("Chunks", help="Number of text chunks"),
            }
        )
        
        # Action buttons in cards
        st.markdown("#### 🎯 Document Actions")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            selected_doc = st.selectbox(
                "Select Document",
                options=[""] + [d["Full ID"] for d in df_data],
                format_func=lambda x: next((d["Name"] for d in df_data if d["Full ID"] == x), "Select...") if x else "Select a document...",
                key="doc_select"
            )
        
        with col2:
            action_cols = st.columns(4)
            with action_cols[0]:
                if st.button("🔍 View", disabled=not selected_doc, use_container_width=True):
                    if selected_doc:
                        doc_details = api_get(f"/documents/{selected_doc}")
                        if doc_details:
                            st.session_state["view_doc_details"] = doc_details
            
            with action_cols[1]:
                if st.button("✏️ Edit", disabled=not selected_doc, use_container_width=True):
                    if selected_doc:
                        st.session_state["edit_doc_id"] = selected_doc
            
            with action_cols[2]:
                if st.button("🔄 Re-process", disabled=not selected_doc, use_container_width=True):
                    st.info("Re-processing feature available in main app")
            
            with action_cols[3]:
                if st.button("🗑️ Delete", disabled=not selected_doc, type="primary", use_container_width=True):
                    if selected_doc:
                        st.session_state["delete_doc_id"] = selected_doc
        
        # Document Details View
        if "view_doc_details" in st.session_state:
            with st.expander("📋 Document Details", expanded=True):
                doc = st.session_state["view_doc_details"]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Document ID:** `{doc.get('document_id', 'N/A')}`")
                    st.markdown(f"**Name:** {doc.get('document_name', 'N/A')}")
                    st.markdown(f"**Status:** {doc.get('status', 'N/A')}")
                    st.markdown(f"**Language:** {doc.get('language', 'N/A')}")
                    st.markdown(f"**Parser:** {doc.get('parser_used', 'N/A')}")
                
                with col2:
                    st.markdown(f"**Chunks:** {doc.get('chunks_created', 0)}")
                    st.markdown(f"**Images:** {doc.get('images_stored', 0)}")
                    st.markdown(f"**Extraction:** {doc.get('extraction_percentage', 0):.1f}%")
                    st.markdown(f"**Processing Time:** {doc.get('processing_time', 0):.2f}s")
                    st.markdown(f"**Created:** {doc.get('created_at', 'N/A')}")
                
                with st.expander("📄 Raw JSON"):
                    st.json(doc)
                
                if st.button("Close", key="close_details"):
                    del st.session_state["view_doc_details"]
                    st.rerun()
        
        # Edit Modal
        if "edit_doc_id" in st.session_state:
            doc_id = st.session_state["edit_doc_id"]
            doc = next((d for d in documents if d.get("document_id") == doc_id), None)
            
            if doc:
                with st.expander("✏️ Edit Document", expanded=True):
                    st.markdown(f"Editing: **{doc.get('document_name', 'Unknown')}**")
                    
                    new_name = st.text_input("Name", value=doc.get("document_name", ""))
                    new_status = st.selectbox(
                        "Status",
                        options=["success", "failed", "processing", "pending"],
                        index=["success", "failed", "processing", "pending"].index(doc.get("status", "pending")) if doc.get("status", "pending") in ["success", "failed", "processing", "pending"] else 0
                    )
                    new_language = st.text_input("Language", value=doc.get("language", "eng"))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save", type="primary"):
                            update_data = {}
                            if new_name != doc.get("document_name"):
                                update_data["document_name"] = new_name
                            if new_status != doc.get("status"):
                                update_data["status"] = new_status
                            if new_language != doc.get("language"):
                                update_data["language"] = new_language
                            
                            if update_data:
                                result = api_put(f"/documents/{doc_id}", update_data)
                                if result:
                                    st.success("✅ Document updated!")
                                    del st.session_state["edit_doc_id"]
                                    st.rerun()
                            else:
                                st.info("No changes to save")
                    
                    with col2:
                        if st.button("Cancel", key="cancel_edit"):
                            del st.session_state["edit_doc_id"]
                            st.rerun()
        
        # Delete Confirmation
        if "delete_doc_id" in st.session_state:
            doc_id = st.session_state["delete_doc_id"]
            doc = next((d for d in documents if d.get("document_id") == doc_id), None)
            
            if doc:
                with st.expander("⚠️ Confirm Deletion", expanded=True):
                    st.warning(f"Delete **{doc.get('document_name', 'Unknown')}**?")
                    
                    delete_vectors = st.checkbox("Delete vector data", value=True)
                    delete_s3 = st.checkbox("Delete S3 files", value=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Confirm Delete", type="primary"):
                            result = api_delete(
                                f"/documents/{doc_id}",
                                params={"delete_vectors": delete_vectors, "delete_s3": delete_s3}
                            )
                            if result:
                                st.success(f"✅ Deleted: {result.get('message', 'Success')}")
                                del st.session_state["delete_doc_id"]
                                st.rerun()
                    
                    with col2:
                        if st.button("Cancel", key="cancel_delete"):
                            del st.session_state["delete_doc_id"]
                            st.rerun()
        
        # Bulk Delete
        with st.expander("🗑️ Bulk Delete"):
            st.warning("⚠️ This action cannot be undone!")
            
            bulk_select = st.multiselect(
                "Select documents",
                options=[d["Full ID"] for d in df_data],
                format_func=lambda x: next((d["Name"] for d in df_data if d["Full ID"] == x), x)
            )
            
            if st.button("🗑️ Delete Selected", type="primary", disabled=len(bulk_select) == 0):
                deleted = 0
                for doc_id in bulk_select:
                    result = api_delete(f"/documents/{doc_id}", params={"delete_vectors": True, "delete_s3": True})
                    if result:
                        deleted += 1
                if deleted > 0:
                    st.success(f"✅ Deleted {deleted} document(s)")
                    st.rerun()
    else:
        st.info("📭 No documents in registry. Upload documents from the main app.")


def render_vector_management():
    """Render Vector Database CRUD section."""
    st.markdown("### 🗄️ Vector Indexes")
    
    # Get vector indexes
    indexes_response = api_get("/admin/indexes", params={"prefix": "aris-"})
    indexes = indexes_response.get("indexes", [])
    
    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">{}</div>
            <div class="stat-label">Total Indexes</div>
        </div>
        """.format(len(indexes)), unsafe_allow_html=True)
    with col2:
        total_chunks = sum(idx.get("chunk_count", 0) for idx in indexes)
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">{}</div>
            <div class="stat-label">Total Chunks</div>
        </div>
        """.format(total_chunks), unsafe_allow_html=True)
    with col3:
        active = sum(1 for idx in indexes if idx.get("status") == "active")
        st.markdown("""
        <div class="stat-card">
            <div class="stat-value">{}</div>
            <div class="stat-label">Active</div>
        </div>
        """.format(active), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if indexes:
        df = pd.DataFrame([{
            "Index": idx.get("index_name", ""),
            "Document": idx.get("document_name", "N/A"),
            "Chunks": idx.get("chunk_count", 0),
            "Dimension": idx.get("dimension", "N/A"),
            "Status": idx.get("status", "unknown")
        } for idx in indexes])
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Actions
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            selected = st.selectbox("Select Index", [""] + [idx.get("index_name") for idx in indexes])
        with col2:
            if st.button("🔍 View Chunks", disabled=not selected, use_container_width=True):
                st.session_state["view_chunks_index"] = selected
        with col3:
            if st.button("🗑️ Delete Index", disabled=not selected, type="primary", use_container_width=True):
                st.session_state["delete_index_name"] = selected
        
        # View Chunks
        if "view_chunks_index" in st.session_state:
            with st.expander(f"📄 Chunks: {st.session_state['view_chunks_index']}", expanded=True):
                chunks_response = api_get(f"/admin/indexes/{st.session_state['view_chunks_index']}/chunks", params={"limit": 20})
                chunks = chunks_response.get("chunks", [])
                st.write(f"Found {chunks_response.get('total', 0)} chunks")
                
                for i, chunk in enumerate(chunks[:10]):
                    with st.expander(f"Chunk {i+1} - Page {chunk.get('page', 'N/A')}"):
                        st.text_area("Content", chunk.get("text", "")[:500], height=100, disabled=True, key=f"chunk_{i}")
                
                if st.button("Close", key="close_chunks"):
                    del st.session_state["view_chunks_index"]
                    st.rerun()
        
        # Delete Index
        if "delete_index_name" in st.session_state:
            with st.expander("⚠️ Delete Index?", expanded=True):
                idx_info = next((idx for idx in indexes if idx.get("index_name") == st.session_state["delete_index_name"]), {})
                st.warning(f"Delete **{st.session_state['delete_index_name']}** ({idx_info.get('chunk_count', 0)} chunks)?")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Confirm", type="primary"):
                        result = api_delete(f"/admin/indexes/{st.session_state['delete_index_name']}", params={"confirm": True})
                        if result:
                            st.success("✅ Index deleted")
                            del st.session_state["delete_index_name"]
                            st.rerun()
                with col2:
                    if st.button("Cancel", key="cancel_idx"):
                        del st.session_state["delete_index_name"]
                        st.rerun()
    else:
        st.info("📭 No vector indexes found.")


def render_search():
    """Render direct vector search."""
    st.markdown("### 🔍 Direct Vector Search")
    
    query = st.text_input("Search Query", placeholder="Enter search query...")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        k = st.slider("Results (k)", 1, 50, 10)
    with col2:
        use_hybrid = st.checkbox("Hybrid Search", value=True)
    with col3:
        semantic_weight = st.slider("Semantic Weight", 0.0, 1.0, 0.7, disabled=not use_hybrid)
    
    if st.button("🔍 Search", type="primary", disabled=not query):
        with st.spinner("Searching..."):
            result = api_post("/admin/search", json_data={
                "query": query,
                "k": k,
                "use_hybrid": use_hybrid,
                "semantic_weight": semantic_weight
            })
            
            if result:
                st.success(f"Found {result.get('total', 0)} results in {result.get('search_time_ms', 0):.1f}ms")
                
                for i, chunk in enumerate(result.get("results", [])[:10]):
                    score = chunk.get('score', 0)
                    with st.expander(f"Result {i+1} - Score: {score:.4f} - {chunk.get('source', 'Unknown')}"):
                        st.markdown(f"**Page:** {chunk.get('page', 'N/A')}")
                        st.text_area("", chunk.get("text", "")[:500], height=100, disabled=True, key=f"res_{i}")


# ============================================================================
# Main App
# ============================================================================

def main():
    # Header
    st.markdown("""
    <div class="admin-header">
        <h1>⚙️ Admin Management</h1>
        <p>Manage documents, vector indexes, and search configuration</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 🔗 Connection")
        
        # Test connection
        try:
            response = requests.get(f"{get_gateway_url()}/health", timeout=5)
            if response.status_code == 200:
                st.success("✅ Gateway Connected")
                health = response.json()
                
                st.markdown("""
                <div class="sidebar-stat">
                    <div class="value">{}</div>
                    <div class="label">Documents</div>
                </div>
                """.format(health.get("registry_document_count", 0)), unsafe_allow_html=True)
            else:
                st.error("❌ Gateway Error")
        except:
            st.warning("⚠️ Gateway Unreachable")
        
        st.divider()
        
        # Quick stats from ingestion
        try:
            stats = api_get("/admin/documents/registry-stats")
            if stats:
                st.markdown("### 📊 Stats")
                st.metric("Total Chunks", stats.get("total_chunks", 0))
                st.metric("Total Images", stats.get("total_images", 0))
        except:
            pass
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📚 Documents", "🗄️ Indexes", "🔍 Search"])
    
    with tab1:
        render_document_management()
    
    with tab2:
        render_vector_management()
    
    with tab3:
        render_search()


if __name__ == "__main__":
    main()
