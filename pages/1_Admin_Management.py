"""
ARIS Admin Management - CRUD Operations for Documents and Vector Database
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
    page_icon="🔧",
    layout="wide"
)

# Configuration
GATEWAY_URL = "http://localhost:8500"  # Default gateway URL

def get_gateway_url():
    """Get gateway URL from session state or environment."""
    import os
    return os.getenv("GATEWAY_URL", GATEWAY_URL)


# ============================================================================
# API Helper Functions
# ============================================================================

def api_get(endpoint: str, params: dict = None) -> dict:
    """Make GET request to Gateway API."""
    try:
        url = f"{get_gateway_url()}{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


def api_post(endpoint: str, data: dict = None, json_data: dict = None) -> dict:
    """Make POST request to Gateway API."""
    try:
        url = f"{get_gateway_url()}{endpoint}"
        response = requests.post(url, data=data, json=json_data, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


def api_put(endpoint: str, json_data: dict) -> dict:
    """Make PUT request to Gateway API."""
    try:
        url = f"{get_gateway_url()}{endpoint}"
        response = requests.put(url, json=json_data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


def api_delete(endpoint: str, params: dict = None) -> dict:
    """Make DELETE request to Gateway API."""
    try:
        url = f"{get_gateway_url()}{endpoint}"
        response = requests.delete(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return {}


# ============================================================================
# UI Components
# ============================================================================

def render_document_management():
    """Render Document Registry CRUD section."""
    st.subheader("📚 Document Registry Management")
    
    # Get documents from registry
    docs_response = api_get("/documents")
    documents = docs_response.get("documents", [])
    
    # Statistics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Documents", len(documents))
    with col2:
        success_count = sum(1 for d in documents if d.get("status") == "success")
        st.metric("Successfully Processed", success_count)
    with col3:
        total_chunks = sum(d.get("chunks_created", 0) for d in documents)
        st.metric("Total Chunks", total_chunks)
    with col4:
        total_images = sum(d.get("images_stored", 0) or d.get("image_count", 0) for d in documents)
        st.metric("Total Images", total_images)
    
    st.divider()
    
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
        
        # Selection
        st.write("**Select documents to manage:**")
        
        # Use data editor for selection
        selection = st.data_editor(
            df[["ID", "Name", "Status", "Language", "Chunks", "Images", "Parser", "Created"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "ID": st.column_config.TextColumn("ID", width="small"),
                "Name": st.column_config.TextColumn("Name", width="medium"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Language": st.column_config.TextColumn("Lang", width="small"),
                "Chunks": st.column_config.NumberColumn("Chunks", width="small"),
                "Images": st.column_config.NumberColumn("Images", width="small"),
                "Parser": st.column_config.TextColumn("Parser", width="small"),
                "Created": st.column_config.TextColumn("Created", width="medium"),
            },
            disabled=True,
            key="doc_table"
        )
        
        # Action buttons
        st.write("**Actions:**")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Single document selection for actions
            selected_doc = st.selectbox(
                "Select document for actions",
                options=[""] + [d["Full ID"] for d in df_data],
                format_func=lambda x: next((d["Name"] for d in df_data if d["Full ID"] == x), "Select a document") if x else "Select a document",
                key="doc_select"
            )
        
        with col2:
            if st.button("🔍 View Details", disabled=not selected_doc, type="secondary"):
                if selected_doc:
                    doc_details = api_get(f"/documents/{selected_doc}")
                    if doc_details:
                        st.session_state["view_doc_details"] = doc_details
        
        with col3:
            if st.button("✏️ Edit Document", disabled=not selected_doc, type="secondary"):
                if selected_doc:
                    st.session_state["edit_doc_id"] = selected_doc
        
        with col4:
            if st.button("🗑️ Delete Document", disabled=not selected_doc, type="primary"):
                if selected_doc:
                    st.session_state["delete_doc_id"] = selected_doc
        
        # Document Details View
        if "view_doc_details" in st.session_state:
            with st.expander("📋 Document Details", expanded=True):
                doc = st.session_state["view_doc_details"]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Document ID:** `{doc.get('document_id', 'N/A')}`")
                    st.write(f"**Name:** {doc.get('document_name', 'N/A')}")
                    st.write(f"**Status:** {doc.get('status', 'N/A')}")
                    st.write(f"**Language:** {doc.get('language', 'N/A')}")
                    st.write(f"**Parser Used:** {doc.get('parser_used', 'N/A')}")
                
                with col2:
                    st.write(f"**Chunks Created:** {doc.get('chunks_created', 0)}")
                    st.write(f"**Images Stored:** {doc.get('images_stored', 0)}")
                    st.write(f"**Extraction %:** {doc.get('extraction_percentage', 0):.1f}%")
                    st.write(f"**Processing Time:** {doc.get('processing_time', 0):.2f}s")
                    st.write(f"**Created:** {doc.get('created_at', 'N/A')}")
                
                # Show full JSON
                with st.expander("Raw JSON"):
                    st.json(doc)
                
                if st.button("Close Details"):
                    del st.session_state["view_doc_details"]
                    st.rerun()
        
        # Edit Document Modal
        if "edit_doc_id" in st.session_state:
            doc_id = st.session_state["edit_doc_id"]
            doc = next((d for d in documents if d.get("document_id") == doc_id), None)
            
            if doc:
                with st.expander("✏️ Edit Document", expanded=True):
                    st.write(f"Editing: **{doc.get('document_name', 'Unknown')}**")
                    
                    new_name = st.text_input("Document Name", value=doc.get("document_name", ""))
                    new_status = st.selectbox(
                        "Status",
                        options=["success", "failed", "processing", "pending"],
                        index=["success", "failed", "processing", "pending"].index(doc.get("status", "pending"))
                    )
                    new_language = st.text_input("Language Code", value=doc.get("language", "eng"))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save Changes", type="primary"):
                            update_data = {}
                            if new_name != doc.get("document_name"):
                                update_data["document_name"] = new_name
                            if new_status != doc.get("status"):
                                update_data["status"] = new_status
                            if new_language != doc.get("language"):
                                update_data["language"] = new_language
                            
                            if update_data:
                                result = api_put(f"/admin/documents/{doc_id}", update_data)
                                if result:
                                    st.success("Document updated successfully!")
                                    del st.session_state["edit_doc_id"]
                                    st.rerun()
                            else:
                                st.info("No changes to save")
                    
                    with col2:
                        if st.button("Cancel"):
                            del st.session_state["edit_doc_id"]
                            st.rerun()
        
        # Delete Confirmation
        if "delete_doc_id" in st.session_state:
            doc_id = st.session_state["delete_doc_id"]
            doc = next((d for d in documents if d.get("document_id") == doc_id), None)
            
            if doc:
                with st.expander("⚠️ Confirm Deletion", expanded=True):
                    st.warning(f"Are you sure you want to delete **{doc.get('document_name', 'Unknown')}**?")
                    
                    delete_vectors = st.checkbox("Also delete vector data (OpenSearch)", value=True)
                    delete_s3 = st.checkbox("Also delete S3 files", value=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Confirm Delete", type="primary"):
                            result = api_delete(
                                f"/admin/documents/{doc_id}",
                                params={"delete_vectors": delete_vectors, "delete_s3": delete_s3}
                            )
                            if result:
                                st.success(f"Document deleted: {result.get('message', 'Success')}")
                                del st.session_state["delete_doc_id"]
                                st.rerun()
                    
                    with col2:
                        if st.button("Cancel Deletion"):
                            del st.session_state["delete_doc_id"]
                            st.rerun()
        
        # Bulk Delete Section
        st.divider()
        with st.expander("🗑️ Bulk Delete Documents"):
            st.warning("⚠️ This action cannot be undone!")
            
            bulk_select = st.multiselect(
                "Select documents to delete",
                options=[d["Full ID"] for d in df_data],
                format_func=lambda x: next((d["Name"] for d in df_data if d["Full ID"] == x), x)
            )
            
            bulk_delete_vectors = st.checkbox("Delete vector data", value=True, key="bulk_vectors")
            bulk_delete_s3 = st.checkbox("Delete S3 files", value=True, key="bulk_s3")
            
            if st.button("🗑️ Delete Selected Documents", type="primary", disabled=len(bulk_select) == 0):
                if bulk_select:
                    result = api_post(
                        "/admin/documents/bulk-delete",
                        json_data={
                            "document_ids": bulk_select,
                            "delete_vectors": bulk_delete_vectors,
                            "delete_s3": bulk_delete_s3
                        }
                    )
                    if result:
                        st.success(f"Bulk delete result: {result.get('message', 'Complete')}")
                        st.rerun()
    else:
        st.info("No documents in registry. Upload documents using the main app.")


def render_vector_management():
    """Render Vector Database CRUD section."""
    st.subheader("🗄️ Vector Database Management")
    
    # Get vector indexes
    indexes_response = api_get("/admin/vectors/indexes", params={"prefix": "aris-"})
    indexes = indexes_response.get("indexes", [])
    
    # Statistics row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Indexes", len(indexes))
    with col2:
        total_chunks = sum(idx.get("chunk_count", 0) for idx in indexes)
        st.metric("Total Chunks", total_chunks)
    with col3:
        active_indexes = sum(1 for idx in indexes if idx.get("status") == "active")
        st.metric("Active Indexes", active_indexes)
    
    st.divider()
    
    # Index List
    if indexes:
        # Create DataFrame
        df_data = []
        for idx in indexes:
            df_data.append({
                "Index Name": idx.get("index_name", ""),
                "Document": idx.get("document_name", "N/A"),
                "Chunks": idx.get("chunk_count", 0),
                "Dimension": idx.get("dimension", "N/A"),
                "Status": idx.get("status", "unknown")
            })
        
        df = pd.DataFrame(df_data)
        
        st.write("**Vector Indexes:**")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Action buttons
        st.write("**Actions:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            selected_index = st.selectbox(
                "Select index for actions",
                options=[""] + [idx["Index Name"] for idx in df_data],
                key="index_select"
            )
        
        with col2:
            if st.button("🔍 View Chunks", disabled=not selected_index, type="secondary"):
                if selected_index:
                    st.session_state["view_chunks_index"] = selected_index
        
        with col3:
            if st.button("🗑️ Delete Index", disabled=not selected_index, type="primary"):
                if selected_index:
                    st.session_state["delete_index_name"] = selected_index
        
        # View Chunks
        if "view_chunks_index" in st.session_state:
            index_name = st.session_state["view_chunks_index"]
            
            with st.expander(f"📄 Chunks in {index_name}", expanded=True):
                offset = st.number_input("Offset", min_value=0, value=0, step=10, key="chunks_offset")
                limit = st.number_input("Limit", min_value=1, max_value=100, value=20, key="chunks_limit")
                
                chunks_response = api_get(
                    f"/admin/vectors/indexes/{index_name}/chunks",
                    params={"offset": offset, "limit": limit}
                )
                
                chunks = chunks_response.get("chunks", [])
                total = chunks_response.get("total", 0)
                
                st.write(f"Showing {len(chunks)} of {total} chunks")
                
                if chunks:
                    for i, chunk in enumerate(chunks):
                        with st.expander(f"Chunk {offset + i + 1}: {chunk.get('chunk_id', 'N/A')[:20]}..."):
                            st.write(f"**Page:** {chunk.get('page', 'N/A')}")
                            st.write(f"**Source:** {chunk.get('source', 'N/A')}")
                            st.write(f"**Language:** {chunk.get('language', 'N/A')}")
                            st.write("**Text:**")
                            st.text_area(
                                "Content",
                                value=chunk.get("text", ""),
                                height=150,
                                key=f"chunk_text_{i}",
                                disabled=True
                            )
                            
                            if st.button(f"🗑️ Delete Chunk", key=f"delete_chunk_{i}"):
                                result = api_delete(f"/admin/vectors/indexes/{index_name}/chunks/{chunk.get('chunk_id')}")
                                if result:
                                    st.success("Chunk deleted")
                                    st.rerun()
                
                if st.button("Close Chunks View"):
                    del st.session_state["view_chunks_index"]
                    st.rerun()
        
        # Delete Index Confirmation
        if "delete_index_name" in st.session_state:
            index_name = st.session_state["delete_index_name"]
            idx_info = next((idx for idx in indexes if idx.get("index_name") == index_name), None)
            
            with st.expander("⚠️ Confirm Index Deletion", expanded=True):
                if idx_info:
                    st.warning(
                        f"Are you sure you want to delete index **{index_name}**?\n\n"
                        f"This will permanently delete **{idx_info.get('chunk_count', 0)} chunks**."
                    )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Confirm Delete Index", type="primary"):
                        result = api_delete(f"/admin/vectors/indexes/{index_name}", params={"confirm": True})
                        if result:
                            st.success(f"Index deleted: {result.get('message', 'Success')}")
                            del st.session_state["delete_index_name"]
                            st.rerun()
                
                with col2:
                    if st.button("Cancel Index Deletion"):
                        del st.session_state["delete_index_name"]
                        st.rerun()
        
        # Bulk Delete Indexes
        st.divider()
        with st.expander("🗑️ Bulk Delete Indexes"):
            st.warning("⚠️ This action cannot be undone! All vector data will be permanently deleted.")
            
            bulk_indexes = st.multiselect(
                "Select indexes to delete",
                options=[idx["Index Name"] for idx in df_data],
                key="bulk_indexes"
            )
            
            if st.button("🗑️ Delete Selected Indexes", type="primary", disabled=len(bulk_indexes) == 0):
                if bulk_indexes:
                    result = api_post(
                        "/admin/vectors/indexes/bulk-delete",
                        json_data={"index_names": bulk_indexes, "confirm": True}
                    )
                    if result:
                        st.success(f"Bulk delete result: {result.get('message', 'Complete')}")
                        st.rerun()
    else:
        st.info("No vector indexes found. Process documents to create indexes.")


def render_vector_search():
    """Render direct vector search section."""
    st.subheader("🔍 Direct Vector Search")
    
    st.write("Search vectors directly without RAG answer generation.")
    
    query = st.text_input("Search Query", placeholder="Enter your search query...")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        k = st.number_input("Results (k)", min_value=1, max_value=100, value=10)
    with col2:
        use_hybrid = st.checkbox("Use Hybrid Search", value=True)
    with col3:
        semantic_weight = st.slider("Semantic Weight", 0.0, 1.0, 0.7, disabled=not use_hybrid)
    
    # Index selection
    indexes_response = api_get("/admin/vectors/indexes", params={"prefix": "aris-"})
    indexes = indexes_response.get("indexes", [])
    index_names = [idx.get("index_name") for idx in indexes]
    
    selected_indexes = st.multiselect(
        "Search in indexes (empty = all)",
        options=index_names,
        default=[]
    )
    
    if st.button("🔍 Search", type="primary", disabled=not query):
        with st.spinner("Searching..."):
            result = api_post(
                "/admin/vectors/search",
                json_data={
                    "query": query,
                    "index_names": selected_indexes if selected_indexes else None,
                    "k": k,
                    "use_hybrid": use_hybrid,
                    "semantic_weight": semantic_weight
                }
            )
            
            if result:
                st.success(f"Found {result.get('total', 0)} results in {result.get('search_time_ms', 0):.2f}ms")
                
                for i, chunk in enumerate(result.get("results", [])):
                    with st.expander(f"Result {i + 1}: Score {chunk.get('score', 'N/A'):.4f}" if chunk.get('score') else f"Result {i + 1}"):
                        st.write(f"**Index:** {chunk.get('index', 'N/A')}")
                        st.write(f"**Source:** {chunk.get('source', 'N/A')}")
                        st.write(f"**Page:** {chunk.get('page', 'N/A')}")
                        st.write("**Text:**")
                        st.text_area("", value=chunk.get("text", ""), height=150, key=f"search_result_{i}", disabled=True)


def render_index_map():
    """Render index map management section."""
    st.subheader("🗺️ Document-Index Mapping")
    
    st.write("Manage the mapping between document names and OpenSearch indexes.")
    
    # Get index map
    map_response = api_get("/admin/vectors/index-map")
    entries = map_response.get("entries", [])
    
    if entries:
        df_data = []
        for entry in entries:
            df_data.append({
                "Document Name": entry.get("document_name", ""),
                "Index Name": entry.get("index_name", ""),
                "Document ID": entry.get("document_id", "N/A")
            })
        
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Delete mapping
        st.write("**Remove Mapping:**")
        col1, col2 = st.columns(2)
        with col1:
            doc_to_remove = st.selectbox(
                "Select document to remove from map",
                options=[""] + [e["Document Name"] for e in df_data],
                key="remove_map_doc"
            )
        with col2:
            if st.button("🗑️ Remove Mapping", disabled=not doc_to_remove):
                if doc_to_remove:
                    result = api_delete(f"/admin/vectors/index-map/{doc_to_remove}")
                    if result:
                        st.success("Mapping removed")
                        st.rerun()
    else:
        st.info("No index mappings found.")
    
    # Add new mapping
    st.divider()
    st.write("**Add/Update Mapping:**")
    
    col1, col2 = st.columns(2)
    with col1:
        new_doc_name = st.text_input("Document Name", placeholder="my-document.pdf")
    with col2:
        new_index_name = st.text_input("Index Name", placeholder="aris-doc-abc123")
    
    if st.button("➕ Add/Update Mapping", disabled=not new_doc_name or not new_index_name):
        result = api_post(
            "/admin/vectors/index-map",
            json_data={"document_name": new_doc_name, "index_name": new_index_name}
        )
        if result:
            st.success("Mapping added/updated")
            st.rerun()


# ============================================================================
# Main App
# ============================================================================

def main():
    st.title("🔧 ARIS Admin Management")
    st.markdown("Manage documents and vector database with full CRUD operations.")
    
    # Connection status
    with st.sidebar:
        st.header("⚙️ Settings")
        gateway_url = st.text_input("Gateway URL", value=get_gateway_url())
        
        # Test connection
        if st.button("🔗 Test Connection"):
            try:
                response = requests.get(f"{gateway_url}/health", timeout=5)
                if response.status_code == 200:
                    st.success("✅ Connected to Gateway")
                    health = response.json()
                    st.json(health)
                else:
                    st.error(f"❌ Gateway returned {response.status_code}")
            except Exception as e:
                st.error(f"❌ Connection failed: {str(e)}")
        
        st.divider()
        st.header("📊 Quick Stats")
        
        # Get quick stats
        try:
            stats = api_get("/admin/documents/registry-stats")
            if stats:
                st.metric("Documents", stats.get("total_documents", 0))
                st.metric("Total Chunks", stats.get("total_chunks", 0))
                st.metric("Total Images", stats.get("total_images", 0))
        except:
            st.warning("Could not load stats")
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📚 Documents",
        "🗄️ Vector Indexes",
        "🔍 Vector Search",
        "🗺️ Index Map"
    ])
    
    with tab1:
        render_document_management()
    
    with tab2:
        render_vector_management()
    
    with tab3:
        render_vector_search()
    
    with tab4:
        render_index_map()


if __name__ == "__main__":
    main()

