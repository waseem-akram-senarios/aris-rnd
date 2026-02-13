"""
Streamlit RAG Application with Advanced Parsers and Real-time Processing
"""
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_API_DIR = str(Path(__file__).resolve().parent)
if _API_DIR in sys.path:
    sys.path.remove(_API_DIR)

import streamlit as st
import os
import io
import json
import pandas as pd
import numpy as np
import time
from dotenv import load_dotenv
from services.ingestion.processor import DocumentProcessor
from services.ingestion.parsers.parser_factory import ParserFactory
from metrics.metrics_collector import MetricsCollector
from shared.utils.chunking_strategies import get_all_strategies, get_chunking_params, validate_custom_params
from shared.config.settings import ARISConfig
from storage.document_registry import DocumentRegistry
from api.service import ServiceContainer  # Unified Service Layer
import logging

load_dotenv()

# Set up logger for app.py
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="ARIS R&D - RAG Document Q&A",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply Custom CSS
from api.styles import get_custom_css, get_glass_card
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Initialize session state
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'citations_history' not in st.session_state:
    st.session_state.citations_history = []  # Store citations for each query
if 'processing_results' not in st.session_state:
    st.session_state.processing_results = []
if 'document_processor' not in st.session_state:
    st.session_state.document_processor = None
if 'metrics_collector' not in st.session_state:
    st.session_state.metrics_collector = MetricsCollector()
if 'document_registry' not in st.session_state:
    st.session_state.document_registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
if 'vectorstore_loaded' not in st.session_state:
    st.session_state.vectorstore_loaded = False
if 'active_sources' not in st.session_state:
    st.session_state.active_sources = []
if 'active_loaded_docs' not in st.session_state:
    st.session_state.active_loaded_docs = []

# AUTO-INITIALIZE: For OpenSearch, enable queries immediately if documents exist in registry
# This allows querying the independent retrieval service without having to "load" documents first
if not st.session_state.documents_processed:
    try:
        existing_docs = st.session_state.document_registry.list_documents()
        if existing_docs and len(existing_docs) > 0:
            # Check if using OpenSearch (independent retrieval)
            vector_store_type = ARISConfig.VECTOR_STORE_TYPE.lower()
            if vector_store_type == 'opensearch':
                # Auto-initialize ServiceContainer for OpenSearch
                if 'service_container' not in st.session_state:
                    st.session_state.service_container = ServiceContainer()
                st.session_state.documents_processed = True
                st.session_state.vectorstore_loaded = True
                logger.info(f"Auto-initialized for OpenSearch: {len(existing_docs)} documents available for querying")
    except Exception as e:
        logger.warning(f"Could not auto-initialize: {e}")

def process_uploaded_files(uploaded_files, use_cerebras, parser_preference, 
                          embedding_model, openai_model, cerebras_model,
                          vector_store_type, opensearch_domain, opensearch_index,
                          chunk_size, chunk_overlap, document_language="eng",
                          force_update=False):
    """Process uploaded files with real-time progress tracking
    
    Args:
        force_update: If True, re-process documents even if they already exist with identical content
    """
    if not uploaded_files:
        return False
    
    # Initialize or update ServiceContainer (which manages GatewayService and DocumentProcessor)
    # Recreate if API, models, embedding model, vector store, or chunking changed
    container = st.session_state.get('service_container')
    
    needs_reinit = (
        container is None or
        (hasattr(container.gateway_service, 'use_cerebras') and container.gateway_service.use_cerebras != use_cerebras) or
        (hasattr(container.gateway_service, 'embedding_model') and container.gateway_service.embedding_model != embedding_model) or
        (hasattr(container.gateway_service, 'openai_model') and container.gateway_service.openai_model != openai_model) or
        (hasattr(container.gateway_service, 'cerebras_model') and container.gateway_service.cerebras_model != cerebras_model) or
        (hasattr(container.gateway_service, 'vector_store_type') and container.gateway_service.vector_store_type != vector_store_type.lower()) or
        (hasattr(container.gateway_service, 'opensearch_domain') and container.gateway_service.opensearch_domain != opensearch_domain) or
        (hasattr(container.gateway_service, 'chunk_size') and getattr(container.gateway_service, 'chunk_size', None) != chunk_size) or
        (hasattr(container.gateway_service, 'chunk_overlap') and getattr(container.gateway_service, 'chunk_overlap', None) != chunk_overlap)
    )
    
    if needs_reinit:
        # Warn if switching vector stores and data exists
        if (container is not None and 
            hasattr(container.gateway_service, 'vector_store_type') and
            container.gateway_service.vector_store_type != vector_store_type.lower() and
            hasattr(container.gateway_service, 'vectorstore') and container.gateway_service.vectorstore is not None):
            st.warning(
                f"⚠️ Switching vector store from {container.gateway_service.vector_store_type.upper()} to {vector_store_type.upper()}. "
                f"Data in the previous store will not be accessible. You may need to reprocess documents."
            )
        
        # Initialize Unified Service Container
        if 'service_container' not in st.session_state:
            container = ServiceContainer()
            st.session_state.service_container = container
        else:
            container = st.session_state.service_container
        
        # Bind components for compatibility
        st.session_state.document_processor = container.document_processor
        st.session_state.metrics_collector = getattr(container, 'metrics_collector', MetricsCollector())
        st.session_state.document_registry = container.document_registry
        
        # Try to load existing vectorstore if FAISS and not already loaded
        if vector_store_type.lower() == 'faiss' and not st.session_state.vectorstore_loaded:
            vectorstore_path = ARISConfig.get_vectorstore_path()
            # load_vectorstore now uses model-specific paths internally
            if os.path.exists(vectorstore_path) or os.path.exists(ARISConfig.get_vectorstore_path(embedding_model)):
                try:
                    loaded = container.gateway_service.load_vectorstore(vectorstore_path)
                    if loaded:
                        st.session_state.vectorstore_loaded = True
                        st.session_state.documents_processed = True
                        # Load existing documents from registry
                        existing_docs = st.session_state.document_registry.list_documents()
                        if existing_docs:
                            st.success(
                                f"📚 **Loaded {len(existing_docs)} document(s) from storage**\n\n"
                                f"✅ Vectorstore loaded\n"
                                f"✅ Documents ready for querying\n"
                                f"💾 All data persisted across restarts\n\n"
                                f"📖 View documents in sidebar under 'Document Library'"
                            )
                except Exception as e:
                    st.warning(f"⚠️ Could not load existing vectorstore: {e}")
    
    # Prepare files for processing
    files_to_process = []
    import tempfile
    temp_files = []  # Keep track of temp files for cleanup
    
    for uploaded_file in uploaded_files:
        file_content = uploaded_file.read()
        file_name = uploaded_file.name
        
        # Validate file content
        if not file_content or len(file_content) == 0:
            import logging
            logging.error(f"File {file_name} has no content (size: {len(file_content) if file_content else 0} bytes)")
            st.error(f"❌ {file_name}: File is empty or could not be read. Please try uploading again.")
            continue
        
        # Save to temporary file for parsers that need file paths
        # This ensures file_path is always a valid path, not just a filename
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1], mode='wb')
        temp_file.write(file_content)
        temp_file.flush()
        os.fsync(temp_file.fileno())  # Ensure data is written to disk
        temp_file.close()
        
        # Verify temp file was created and has content
        if not os.path.exists(temp_file.name):
            import logging
            logging.error(f"Temp file was not created: {temp_file.name}")
            st.error(f"❌ {file_name}: Failed to create temporary file. Please try again.")
            continue
        
        file_size = os.path.getsize(temp_file.name)
        if file_size == 0:
            import logging
            logging.error(f"Temp file is empty: {temp_file.name} (expected {len(file_content)} bytes)")
            st.error(f"❌ {file_name}: Temporary file is empty. Please try uploading again.")
            os.unlink(temp_file.name)  # Clean up empty file
            continue
        
        if file_size != len(file_content):
            import logging
            logging.warning(f"Temp file size mismatch: {file_size} bytes written, expected {len(file_content)} bytes")
        
        temp_files.append(temp_file.name)  # Track for potential cleanup
        
        # Calculate file hash for duplicate detection
        import hashlib
        file_hash = hashlib.md5(file_content).hexdigest()
        
        files_to_process.append({
            'path': temp_file.name,  # Use actual temp file path
            'content': file_content,  # Also keep content for parsers that prefer it
            'name': file_name,
            'file_hash': file_hash
        })
    
    # Check for duplicates before processing
    registry = st.session_state.get('document_registry')
    if registry is None:
        from storage.document_registry import DocumentRegistry
        registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
        st.session_state.document_registry = registry
    
    files_after_duplicate_check = []
    effective_parser = parser_preference.lower() if parser_preference else 'pymupdf'
    
    for file_info in files_to_process:
        file_name = file_info['name']
        file_hash = file_info['file_hash']
        
        # Check for existing document with same name and parser
        existing_doc = registry.find_document_by_name_and_parser(file_name, effective_parser)
        
        if existing_doc:
            if existing_doc.get('file_hash') == file_hash and not force_update:
                # Exact same file and force_update is False - skip
                st.warning(f"⚠️ **{file_name}** already exists with identical content (Parser: {effective_parser}). Skipping upload. Enable 'Force Update' to re-process.")
                # Clean up temp file
                if os.path.exists(file_info['path']):
                    os.unlink(file_info['path'])
                continue
            elif existing_doc.get('file_hash') == file_hash and force_update:
                # Exact same file but force_update is True - update anyway
                file_info['is_update'] = True
                file_info['old_document_id'] = existing_doc.get('document_id')
                file_info['old_index_name'] = existing_doc.get('index_name')
                st.info(f"🔄 **{file_name}** exists with identical content. **Force updating** (re-processing)...")
            else:
                # Same name/parser but different content - will update
                file_info['is_update'] = True
                file_info['old_document_id'] = existing_doc.get('document_id')
                file_info['old_index_name'] = existing_doc.get('index_name')
                st.info(f"🔄 **{file_name}** exists with different content. Will **update** the existing document.")
        else:
            # Check if same filename exists with different parser
            all_versions = registry.find_documents_by_name(file_name)
            if all_versions:
                parser_list = [d.get('parser_used', 'unknown') for d in all_versions]
                st.info(f"ℹ️ **{file_name}** exists with parser(s): {parser_list}. Creating new version with **{effective_parser}**.")
            file_info['is_update'] = False
        
        files_after_duplicate_check.append(file_info)
    
    # Update files_to_process with the filtered list
    files_to_process = files_after_duplicate_check
    
    if not files_to_process:
        st.info("No new documents to process. All files already exist with identical content.")
        return False
    
    # Process files with progress tracking
    results = []
    progress_container = st.container()
    
    with progress_container:
        for idx, file_info in enumerate(files_to_process):
            file_name = file_info['name']
            
            # Show progress for this file
            with st.expander(f"📄 Processing: {file_name} ({idx + 1}/{len(files_to_process)})", expanded=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Store last detailed status message from parser
                detailed_status = st.empty()
                
                # Track processing start time and last update time for frequent updates
                import time
                processing_start_time = time.time()
                last_update_time = time.time()
                last_progress = 0.0
                
                def progress_callback(status, progress, **kwargs):
                    nonlocal last_update_time, last_progress
                    detailed_message = kwargs.get('detailed_message', None)
                    current_time = time.time()
                    
                    # Update progress bar immediately
                    progress_bar.progress(progress)
                    
                    # Force update every 0.5 seconds or if progress changed significantly
                    progress_changed = abs(progress - last_progress) > 0.01
                    time_since_last_update = current_time - last_update_time
                    total_elapsed_time = current_time - processing_start_time
                    
                    if progress_changed or time_since_last_update >= 0.5:
                        last_update_time = current_time
                        last_progress = progress
                        
                        # Build status message with more details
                        progress_percent = int(progress * 100)
                        elapsed_seconds = int(total_elapsed_time)
                        
                        status_messages = {
                            'parsing': f'🔍 Parsing document... ({progress_percent}%)',
                            'chunking': f'✂️ Chunking text... ({progress_percent}%)',
                            'embedding': f'🧮 Creating embeddings... ({progress_percent}%)',
                            'complete': '✅ Complete!',
                            'failed': '❌ Failed',
                            'processing': f'⏳ Processing... ({progress_percent}%)'
                        }
                        message = status_messages.get(status, f'Processing... ({progress_percent}%)')
                        
                        # Add special message for Docling with time estimate
                        if parser_preference and parser_preference.lower() == 'docling' and status == 'parsing':
                            if elapsed_seconds > 0:
                                minutes = elapsed_seconds // 60
                                seconds = elapsed_seconds % 60
                                time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                                message = f'🔍 Docling parsing... ({progress_percent}%) - Processing all pages (elapsed: {time_str}, estimated: 5-10 min)'
                            else:
                                message = f'🔍 Docling parsing... ({progress_percent}%) - Processing all pages (estimated: 5-10 min)'
                        # Add special message for PyMuPDF
                        elif parser_preference and parser_preference.lower() == 'pymupdf' and status == 'parsing':
                            if elapsed_seconds > 0:
                                minutes = elapsed_seconds // 60
                                seconds = elapsed_seconds % 60
                                time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                                message = f'🔍 PyMuPDF parsing... ({progress_percent}%) - (elapsed: {time_str})'
                            else:
                                message = f'🔍 PyMuPDF parsing... ({progress_percent}%)'
                        # Add more detailed messages for chunking/embedding
                        elif status == 'chunking':
                            if elapsed_seconds > 0:
                                minutes = elapsed_seconds // 60
                                seconds = elapsed_seconds % 60
                                time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                                message = f'✂️ Chunking text... ({progress_percent}%) - Splitting into chunks (elapsed: {time_str})'
                            else:
                                message = f'✂️ Chunking text... ({progress_percent}%) - Splitting into chunks'
                        elif status == 'embedding':
                            if elapsed_seconds > 0:
                                minutes = elapsed_seconds // 60
                                seconds = elapsed_seconds % 60
                                time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
                                message = f'🧮 Creating embeddings... ({progress_percent}%) - Generating vector embeddings (elapsed: {time_str})'
                            else:
                                message = f'🧮 Creating embeddings... ({progress_percent}%) - Generating vector embeddings'
                        
                        status_text.text(message)
                        
                        # Show detailed status from parser if available
                        if detailed_message:
                            detailed_status.info(f"📊 {detailed_message}")
                        elif status == 'parsing' and parser_preference and parser_preference.lower() == 'pymupdf':
                            # Clear detailed status when not parsing
                            detailed_status.empty()
                    
                    # Always update detailed message if provided (even if time hasn't elapsed)
                    if detailed_message:
                        detailed_status.info(f"📊 {detailed_message}")
                
                # Handle OpenSearch index name generation from document name
                container = st.session_state.get('service_container')
                if vector_store_type.lower() == 'opensearch' and container:
                    try:
                        # Use static method for sanitization only - no instantiation
                        from vectorstores.opensearch_store import OpenSearchVectorStore
                        
                        # Generate index name from document name
                        base_index_name = OpenSearchVectorStore.sanitize_index_name(file_name)
                        
                        # Use session state to track user's choice for this document
                        choice_key = f"index_choice_{file_name}"
                        if choice_key not in st.session_state:
                            st.session_state[choice_key] = None
                        
                        # Check if user has already made a choice
                        if st.session_state[choice_key] is None:
                            # Check if index exists via Gateway/Ingestion service
                            # Using Gateway's proxy to avoid direct DB connection from UI
                            index_exists = False
                            if hasattr(container, 'index_exists'):
                                index_exists = container.index_exists(base_index_name)
                            
                            # If index exists, ask user what to do
                            if index_exists:
                                # Check if choice was already made in a previous run
                                if st.session_state[choice_key] is None:
                                    st.info(f"📇 Index '{base_index_name}' already exists for this document.")
                                    
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        update_clicked = st.button(
                                            "🔄 Update Existing Index",
                                            key=f"update_index_{file_name}",
                                            help="Replace existing data in the index"
                                        )
                                        if update_clicked:
                                            st.session_state[choice_key] = "update"
                                            st.rerun()
                                    with col2:
                                        new_clicked = st.button(
                                            "➕ Create New Index (Auto-increment)",
                                            key=f"new_index_{file_name}",
                                            help="Create a new index with auto-incremented name"
                                        )
                                        if new_clicked:
                                            st.session_state[choice_key] = "new"
                                            st.rerun()
                                    
                                    # Wait for user decision - only stop if no choice has been made
                                    st.stop()
                            else:
                                # Index doesn't exist, use the base name
                                final_index_name = base_index_name
                                # Set opensearch_index if it's settable
                                if hasattr(container, 'opensearch_index'):
                                    try:
                                        container.opensearch_index = final_index_name
                                    except AttributeError:
                                        # If it's a read-only property, log warning but continue
                                        logger.warning(f"Could not set opensearch_index (read-only), using: {final_index_name}")
                                st.info(f"📇 Using index: `{final_index_name}`")
                                # Clear choice key since we're done
                                if choice_key in st.session_state:
                                    del st.session_state[choice_key]
                        
                        # User has made a choice (index existed), process it
                        if choice_key in st.session_state and st.session_state[choice_key] is not None:
                            if st.session_state[choice_key] == "update":
                                # Use existing index name
                                final_index_name = base_index_name
                            elif st.session_state[choice_key] == "new":
                                # Find next available index name via Gateway
                                if hasattr(container, 'find_next_available_index_name'):
                                    final_index_name = container.find_next_available_index_name(base_index_name)
                                else:
                                    final_index_name = f"{base_index_name}-1"
                            else:
                                # No choice made yet (shouldn't happen, but fallback)
                                final_index_name = base_index_name
                            
                            # Update RAGSystem's opensearch_index
                            if hasattr(container, 'opensearch_index'):
                                try:
                                    container.opensearch_index = final_index_name
                                except AttributeError:
                                    # If it's a read-only property, log warning but continue
                                    logger.warning(f"Could not set opensearch_index (read-only), using: {final_index_name}")
                            st.success(f"✅ Using index: `{final_index_name}`")
                            # Clear the choice after using it
                            del st.session_state[choice_key]
                            
                    except Exception as e:
                        st.warning(f"⚠️ Could not generate index name from document name: {str(e)}. Using default index.")
                        # Continue with default index
                
                # Process document with error handling
                try:
                    # Ensure document_processor is initialized
                    if st.session_state.document_processor is None:
                        # Initialize ServiceContainer if not already done
                        if 'service_container' not in st.session_state or st.session_state.service_container is None:
                            st.session_state.service_container = ServiceContainer()
                        st.session_state.document_processor = st.session_state.service_container.document_processor
                    
                    # Show processing status immediately
                    is_update = file_info.get('is_update', False)
                    old_index_name = file_info.get('old_index_name')
                    
                    update_msg = " (updating existing document)" if is_update else ""
                    processing_status = st.info(f"🔄 Processing {file_name}{update_msg}...")
                    
                    # Process document (this may take time for large documents)
                    result = st.session_state.document_processor.process_document(
                        file_path=file_info['path'],
                        file_content=file_info['content'],
                        file_name=file_name,
                        parser_preference=parser_preference,
                        progress_callback=progress_callback,
                        index_name=final_index_name if 'final_index_name' in locals() else opensearch_index,
                        language=document_language,
                        is_update=is_update,
                        old_index_name=old_index_name
                    )
                    
                    # Clear processing status immediately after completion
                    processing_status.empty()
                    
                    # Verify result is valid
                    if result is None:
                        raise ValueError("Processing returned None result")
                    
                    results.append(result)
                    
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    logger.error(f"Error processing {file_name}: {error_details}")
                    st.error(f"❌ Error processing {file_name}: {str(e)}")
                    # Create a failed result
                    from shared.schemas import ProcessingResult
                    result = ProcessingResult(
                        status='failed',
                        document_name=file_name,
                        error=str(e),
                        chunks_created=0,
                        tokens_extracted=0
                    )
                    results.append(result)
                
                # Save to shared document registry if successful
                if result.status == 'success':
                    import uuid
                    document_id = str(uuid.uuid4())
                    # Get pages from metrics if available
                    pages = None
                    if st.session_state.metrics_collector.processing_metrics:
                        for metric in reversed(st.session_state.metrics_collector.processing_metrics):
                            if metric.document_name == result.document_name:
                                pages = metric.pages
                                break
                    
                    doc_metadata = {
                        'document_id': document_id,
                        'document_name': result.document_name,
                        'status': result.status,
                        'chunks_created': result.chunks_created,
                        'tokens_extracted': result.tokens_extracted,
                        'parser_used': result.parser_used,
                        'processing_time': result.processing_time,
                        'extraction_percentage': result.extraction_percentage,
                        'images_detected': result.images_detected,
                        'pages': pages,
                        'error': result.error
                    }
                    st.session_state.document_registry.add_document(document_id, doc_metadata)
                
                # Show result summary
                if result.status == 'success':
                    parser_info = f"Parser: {result.parser_used}"
                    if result.parser_used == "docling":
                        parser_info += " (processed all pages)"
                    st.success(
                        f"✅ {file_name}: {result.chunks_created} chunks, "
                        f"{result.tokens_extracted:,} tokens, "
                        f"{parser_info}"
                    )
                    if result.images_detected:
                        st.warning("⚠️ Images detected in PDF")
                else:
                    st.error(f"❌ {file_name}: {result.error}")
    
    # Update session state
    st.session_state.processing_results.extend(results)
    # Clean up temporary files
    for temp_file_path in temp_files:
        try:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except Exception as e:
            import logging
            logging.warning(f"Could not delete temp file {temp_file_path}: {str(e)}")
    
    successful_results = [r for r in results if r.status == 'success']
    
    if successful_results:
        st.session_state.documents_processed = True
        # Ensure container exists in session state after processing
        if 'service_container' not in st.session_state:
            st.session_state.service_container = ServiceContainer()
        total_chunks = sum(r.chunks_created for r in successful_results)
        total_tokens = sum(r.tokens_extracted for r in successful_results)
        st.success(
            f"✅ Processed {len(successful_results)} document(s) into {total_chunks} chunks "
            f"({total_tokens:,} tokens)!"
        )

        # Default to the most recently processed document for Q&A / summary queries
        try:
            last_doc_name = successful_results[-1].document_name
            if last_doc_name:
                st.session_state.active_sources = [last_doc_name]
                st.session_state.active_loaded_docs = [last_doc_name]
                container = st.session_state.get('service_container')
                if container:
                    # Set active sources for filtering
                    container.gateway_service.active_sources = [last_doc_name]
                    # For OpenSearch, ensure per-document index selection is active
                    if getattr(container.gateway_service, 'vector_store_type', '').lower() == 'opensearch':
                        try:
                            result = container.gateway_service.load_selected_documents(
                                document_names=[last_doc_name],
                                path=ARISConfig.VECTORSTORE_PATH
                            )
                            # Log success for debugging
                            if result.get('loaded'):
                                logger.info(f"✅ OpenSearch document loaded: {result.get('message', '')}")
                        except Exception as e:
                            logger.warning(f"Could not load OpenSearch document: {e}")
                    # Mark vectorstore as loaded for both FAISS and OpenSearch
                    st.session_state.vectorstore_loaded = True
        except Exception as e:
            logger.warning(f"Error setting active sources: {e}")
        
        # Save vectorstore to disk for sharing with FastAPI (FAISS only)
        # OpenSearch stores data in cloud, so no local save needed
        container = st.session_state.get('service_container')
        if (container and 
            hasattr(container.gateway_service, 'vectorstore') and container.gateway_service.vectorstore and 
            container.gateway_service.vector_store_type.lower() == 'faiss'):
            try:
                vectorstore_path = ARISConfig.get_vectorstore_path()
                container.gateway_service.save_vectorstore(vectorstore_path)
                st.session_state.vectorstore_loaded = True
                st.caption("💾 Vectorstore saved to shared storage")
            except Exception as e:
                st.warning(f"⚠️ Could not save vectorstore: {e}")
        elif (container and 
              container.gateway_service.vector_store_type.lower() == 'opensearch'):
            # OpenSearch stores data in cloud - already persisted
            st.session_state.vectorstore_loaded = True
            opensearch_domain = getattr(container.gateway_service, 'opensearch_domain', 'N/A')
            opensearch_index = getattr(container.gateway_service, 'opensearch_index', 'N/A')
            st.caption(f"☁️ Vectorstore saved to OpenSearch Cloud (Domain: {opensearch_domain}, Index: {opensearch_index})")
        elif container:
            # For any other case, still mark as loaded if container exists
            st.session_state.vectorstore_loaded = True
        
        return True
    else:
        st.error("No documents were successfully processed.")
        return False

# Main UI
# Main UI - Custom Hero Header
st.markdown("""
<div class="hero-header">
    <div class="hero-title">ARIS R&D</div>
    <div class="hero-subtitle">Next-Generation RAG Document Intelligence System</div>
</div>
""", unsafe_allow_html=True)
# st.markdown("Upload documents and ask questions about them using AI with advanced parsers!")

# Sidebar for settings
with st.sidebar:
    st.markdown("### ⚙️ Control Panel")
    
    # MCP Server Status Indicator
    if 'mcp_status_last_check' not in st.session_state:
        st.session_state.mcp_status_last_check = 0
        st.session_state.mcp_is_online = False
    
    # Check status every 30 seconds
    import time
    if time.time() - st.session_state.mcp_status_last_check > 30:
        try:
             # Use ServiceContainer if available
             if 'service_container' not in st.session_state:
                 st.session_state.service_container = ServiceContainer()
             
             # Quick check
             from services.gateway.service import GatewayService
             # We can't access gateway_service directly if we don't have the instance easily, 
             # but we can use st.session_state.service_container
             status = st.session_state.service_container.get_mcp_status()
             st.session_state.mcp_is_online = status.get("status") == "healthy" or status.get("status") == "ok"
             st.session_state.mcp_status_last_check = time.time()
        except Exception:
             st.session_state.mcp_is_online = False
    
    # Display Status
    mcp_color = "🟢" if st.session_state.mcp_is_online else "🔴"
    mcp_text = "Online" if st.session_state.mcp_is_online else "Offline"
    st.caption(f"MCP Server: {mcp_color} {mcp_text}")
    
    # API selection (use shared config default)
    default_api = "Cerebras" if ARISConfig.USE_CEREBRAS else "OpenAI"
    api_choice = st.radio(
        "Choose API:",
        ["OpenAI", "Cerebras"],
        index=1 if ARISConfig.USE_CEREBRAS else 0,
        help="Select which API to use for generating answers"
    )
    use_cerebras = api_choice == "Cerebras"
    
    # Model selection based on API choice
    st.markdown("---")
    st.markdown("### 🤖 Model Settings")
    
    # Model descriptions
    openai_models = {
        "gpt-3.5-turbo": "Fast and cost-effective. Good for most tasks. Best balance of speed and quality.",
        "gpt-4": "More capable than GPT-3.5. Better for complex reasoning and detailed analysis.",
        "gpt-4-turbo-preview": "GPT-4 variant with improved performance. Best for complex queries.",
        "gpt-4o": "Optimized GPT-4 model. Faster responses with GPT-4 quality.",
        "gpt-4o-mini": "Smaller, faster version. Good for simple queries with lower cost.",
        "gpt-4o-2024-08-06": "Latest GPT-4o model (August 2024). Most recent improvements and features."
    }
    
    cerebras_models = {
        "llama3.1-8b": "Fast 8B parameter model. Good balance of speed and quality. Best for most tasks.",
        "llama-3.3-70b": "Large 70B parameter model. More capable for complex reasoning. Slower but higher quality.",
        "qwen-3-32b": "32B parameter model. Alternative option with good performance.",
        "gpt-oss-120b": "Open-source 120B parameter model. Very large context (~3000 tokens). Best for complex, long-form analysis and reasoning."
    }
    
    embedding_models = {
        "text-embedding-3-small": "Cost-effective embedding model. 1536 dimensions. Best for most use cases.",
        "text-embedding-3-large": "Higher quality embeddings. 3072 dimensions. Better accuracy, higher cost.",
        "text-embedding-ada-002": "Legacy model. 1536 dimensions. Still reliable but older technology."
    }
    
    if api_choice == "OpenAI":
        # Use shared config default
        default_openai_index = list(openai_models.keys()).index(ARISConfig.OPENAI_MODEL) if ARISConfig.OPENAI_MODEL in openai_models else 0
        openai_model = st.selectbox(
            "OpenAI Model:",
            list(openai_models.keys()),
            index=default_openai_index,
            help="Select OpenAI model for generating answers"
        )
        # Show description
        with st.expander("ℹ️ Model Description", expanded=False):
            st.write(f"**{openai_model}**")
            st.write(openai_models[openai_model])
        cerebras_model = ARISConfig.CEREBRAS_MODEL  # Default, not used
    else:
        # Use shared config default
        default_cerebras_index = list(cerebras_models.keys()).index(ARISConfig.CEREBRAS_MODEL) if ARISConfig.CEREBRAS_MODEL in cerebras_models else 0
        cerebras_model = st.selectbox(
            "Cerebras Model:",
            list(cerebras_models.keys()),
            index=default_cerebras_index,
            help="Select Cerebras model for generating answers"
        )
        # Show description
        with st.expander("ℹ️ Model Description", expanded=False):
            st.write(f"**{cerebras_model}**")
            st.write(cerebras_models[cerebras_model])
        openai_model = ARISConfig.OPENAI_MODEL  # Default, not used
    
    # Embedding model selection (use shared config default)
    default_embedding_index = list(embedding_models.keys()).index(ARISConfig.EMBEDDING_MODEL) if ARISConfig.EMBEDDING_MODEL in embedding_models else 0
    embedding_model = st.selectbox(
        "Embedding Model:",
        list(embedding_models.keys()),
        index=default_embedding_index,
        help="Select embedding model for document vectors"
    )
    # Show embedding model description
    with st.expander("ℹ️ Embedding Model Description", expanded=False):
        st.write(f"**{embedding_model}**")
        st.write(embedding_models[embedding_model])
    
    # Multilingual selection
    st.divider()
    st.header("🌍 Multilingual Settings")
    
    # Response Language with more options
    response_language_options = {
        "Auto": "🔄 Auto (same as query language)",
        "English": "🇬🇧 English",
        "Spanish": "🇪🇸 Spanish",
        "French": "🇫🇷 French",
        "German": "🇩🇪 German",
        "Italian": "🇮🇹 Italian",
        "Portuguese": "🇵🇹 Portuguese",
        "Dutch": "🇳🇱 Dutch",
        "Russian": "🇷🇺 Russian",
        "Chinese": "🇨🇳 Chinese",
        "Japanese": "🇯🇵 Japanese",
        "Korean": "🇰🇷 Korean",
        "Arabic": "🇸🇦 Arabic",
        "Hindi": "🇮🇳 Hindi",
        "Turkish": "🇹🇷 Turkish",
        "Vietnamese": "🇻🇳 Vietnamese",
        "Thai": "🇹🇭 Thai",
        "Greek": "🇬🇷 Greek",
        "Polish": "🇵🇱 Polish",
        "Ukrainian": "🇺🇦 Ukrainian",
    }
    response_languages = list(response_language_options.keys())
    
    response_language = st.selectbox(
        "Preferred Response Language:",
        options=response_languages,
        format_func=lambda x: response_language_options.get(x, x),
        index=0,
        help="Language for the AI's response. Select 'Auto' to respond in the same language as your query."
    )
    
    # Handle 'Auto' response language
    if response_language == "Auto":
        response_language = None  # Will be set dynamically based on query language
    
    # Auto-Translation Toggle
    col1, col2 = st.columns(2)
    
    with col1:
        auto_translate = st.toggle(
            "Auto-Translate Queries",
            value=True,  # Enabled by default based on R&D testing (70%+ accuracy for cross-language)
            help="If enabled, non-English queries are translated to English for better semantic search retrieval. "
                 "The original query is preserved for keyword matching (dual-search). "
                 "Recommended: Keep enabled for cross-language queries."
        )
    
    with col2:
        enable_dual_search = st.toggle(
            "Dual-Language Search",
            value=True,
            help="When enabled, searches use both the translated query (for semantic search) and original query "
                 "(for keyword matching). This improves cross-lingual retrieval accuracy."
        )
    
    # Language Filter with expanded options
    filter_language_options = {
        "All": "🌐 All Languages",
        "eng": "🇬🇧 English",
        "spa": "🇪🇸 Spanish",
        "fra": "🇫🇷 French",
        "deu": "🇩🇪 German",
        "ita": "🇮🇹 Italian",
        "por": "🇵🇹 Portuguese",
        "rus": "🇷🇺 Russian",
        "zho": "🇨🇳 Chinese",
        "jpn": "🇯🇵 Japanese",
        "kor": "🇰🇷 Korean",
        "ara": "🇸🇦 Arabic",
    }
    
    filter_language = st.selectbox(
        "Filter by Document Language:",
        options=list(filter_language_options.keys()),
        format_func=lambda x: filter_language_options.get(x, x),
        index=0,
        help="Restrict search to documents of a specific language. Documents are tagged with language during ingestion."
    )
    if filter_language == "All":
        filter_language = None
    
    # Parser selection
    st.divider()
    st.header("🔧 Parser Settings")
    parser_choice = st.selectbox(
        "Choose Parser:",
        ["Docling", "PyMuPDF", "OCRmyPDF", "Llama-Scan", "Textract"],
        index=0,  # Default to Docling for best accuracy (100% in benchmarks)
        key="parser_choice_v2",
        help="**Docling**: Primary recommended parser. Achieved **100% page accuracy** in benchmarks. Processes all content reliably.\n\n"
             "**PyMuPDF**: Fastest parser. Best for quick previews and text-heavy PDFs where speed is priority.\n\n"
             "**OCRmyPDF**: Optimized OCR with Tesseract - best for scanned PDFs. "
             "Includes automatic deskew and rotation correction.\n\n"
             "**Llama-Scan**: Multimodal PDF parsing via Llama-3 vision models. Excellent for **complex tables/diagrams**.\n\n"
             "**Textract**: AWS Textract (requires credentials) - best for industry-scale scanned documents."
    )
    if parser_choice == "Llama-Scan":
        parser_preference = "llamascan"
    else:
        parser_preference = parser_choice.lower()
    
    # OCR settings for OCRmyPDF
    # Initialize session state for document language if not set
    if 'last_document_language' not in st.session_state:
        st.session_state.last_document_language = 'eng'
    
    ocr_languages_default = "eng"  # Default, will be updated based on document language
    ocr_dpi = 300
    
    if parser_choice == "OCRmyPDF":
        with st.expander("🔍 OCR Settings", expanded=True):
            # Get document language from session state (set in upload section below)
            current_doc_lang = st.session_state.get('last_document_language', 'eng')
            
            # Convert document language to Tesseract format
            try:
                from services.language.detector import get_detector
                detector = get_detector()
                tesseract_lang = detector.get_ocr_language(current_doc_lang)
                # For non-English, add English as fallback for better accuracy
                if tesseract_lang != "eng":
                    ocr_languages_default = f"{tesseract_lang}+eng"
                else:
                    ocr_languages_default = "eng"
            except Exception as e:
                # Fallback if detector not available
                logger.warning(f"Could not get OCR language from detector: {e}")
                # Direct mapping for common languages
                lang_map = {
                    'eng': 'eng', 'spa': 'spa+eng', 'fra': 'fra+eng', 'deu': 'deu+eng',
                    'ita': 'ita+eng', 'por': 'por+eng', 'rus': 'rus+eng', 'jpn': 'jpn+eng',
                    'kor': 'kor+eng', 'zho': 'chi_sim+eng', 'ara': 'ara+eng'
                }
                ocr_languages_default = lang_map.get(current_doc_lang, 'eng')
            
            # Check if OCR languages key exists in session state, if not use default
            ocr_lang_key = "ocr_languages_value"
            if ocr_lang_key not in st.session_state:
                st.session_state[ocr_lang_key] = ocr_languages_default
            
            # Update OCR languages if document language changed
            if current_doc_lang != st.session_state.get('previous_doc_lang', ''):
                st.session_state[ocr_lang_key] = ocr_languages_default
                st.session_state.previous_doc_lang = current_doc_lang
            
            ocr_languages = st.text_input(
                "Tesseract Languages:",
                value=st.session_state.get(ocr_lang_key, ocr_languages_default),
                key="ocr_languages_input",
                help="Language codes for Tesseract OCR. Auto-synced with Document Language (see Upload section below). "
                     "Examples: 'eng' (English), 'spa+eng' (Spanish+English), 'fra+eng' (French+English). "
                     "💡 **Tip:** Change Document Language in the Upload section to auto-update this field."
            )
            ocr_dpi = st.slider(
                "OCR DPI:",
                min_value=150,
                max_value=600,
                value=300,
                step=50,
                help="DPI for OCR processing. Higher DPI = better accuracy but slower. 300 DPI is recommended."
            )
            
            # Show current language info
            lang_display = {
                'eng': 'English', 'spa': 'Spanish', 'fra': 'French', 'deu': 'German',
                'ita': 'Italian', 'por': 'Portuguese', 'rus': 'Russian', 'jpn': 'Japanese',
                'kor': 'Korean', 'zho': 'Chinese', 'ara': 'Arabic'
            }
            current_lang_name = lang_display.get(current_doc_lang, current_doc_lang)
            
            st.info(f"💡 **OCRmyPDF Features:**\n"
                   "- Automatic deskew and rotation correction\n"
                   "- Noise removal for better accuracy\n"
                   "- Text layer embedding in PDFs\n"
                   "- Optimized for scanned documents\n"
                   f"- **Document Language:** {current_lang_name} ({current_doc_lang})\n"
                   f"- **OCR Languages:** {ocr_languages} (auto-synced, change Document Language below to update)")
            
            # Store current OCR languages in session state
            st.session_state[ocr_lang_key] = ocr_languages
    else:
        ocr_languages = "eng"
        ocr_dpi = 300

    if parser_choice == "Llama-Scan":
        with st.expander("🦙 Llama-Scan Settings", expanded=True):
            llama_model = st.text_input(
                "Ollama Model:",
                value=os.getenv("LLAMA_SCAN_MODEL", "qwen2.5vl:latest"),
                help="Vision model name in Ollama. Example: qwen2.5vl:latest"
            )
            ollama_url = st.text_input(
                "Ollama Server URL:",
                value=os.getenv("OLLAMA_SERVER_URL", "http://localhost:11434"),
                help="Ollama server endpoint reachable from the app container."
            )
            include_diagrams = st.checkbox(
                "Include diagram/image descriptions",
                value=os.getenv("LLAMA_SCAN_INCLUDE_DIAGRAMS", "true").strip().lower() in {"1", "true", "yes", "y", "on"},
                help="If enabled, model will describe diagrams/images using <image> tags."
            )
            start_page = st.number_input(
                "Start Page (0 = first)",
                min_value=0,
                value=int(os.getenv("LLAMA_SCAN_START_PAGE", "0")),
                step=1
            )
            end_page = st.number_input(
                "End Page (0 = last)",
                min_value=0,
                value=int(os.getenv("LLAMA_SCAN_END_PAGE", "0")),
                step=1
            )
            resize_width = st.number_input(
                "Resize Width (0 = no resize)",
                min_value=0,
                value=int(os.getenv("LLAMA_SCAN_WIDTH", "0")),
                step=50
            )
            custom_instructions = st.text_area(
                "Custom Instructions (optional)",
                value=os.getenv("LLAMA_SCAN_CUSTOM_INSTRUCTIONS", ""),
                help="Extra instructions appended to the transcription prompt."
            )
        os.environ["LLAMA_SCAN_MODEL"] = str(llama_model).strip() or "qwen2.5vl:latest"
        os.environ["OLLAMA_SERVER_URL"] = str(ollama_url).strip() or "http://localhost:11434"
        os.environ["LLAMA_SCAN_INCLUDE_DIAGRAMS"] = "true" if include_diagrams else "false"
        os.environ["LLAMA_SCAN_START_PAGE"] = str(int(start_page))
        os.environ["LLAMA_SCAN_END_PAGE"] = str(int(end_page))
        os.environ["LLAMA_SCAN_WIDTH"] = str(int(resize_width))
        os.environ["LLAMA_SCAN_CUSTOM_INSTRUCTIONS"] = str(custom_instructions or "").strip()
    
    # Document Library - Long-term Storage Review
    st.divider()
    st.header("📚 Document Library")
    
    # Initialize vector_store_choice in session state if not set (for use in Document Library)
    if 'vector_store_choice' not in st.session_state:
        st.session_state.vector_store_choice = "OpenSearch" if ARISConfig.VECTOR_STORE_TYPE.lower() == "opensearch" else "FAISS"
    
    # Load and display stored documents
    if 'document_registry' in st.session_state:
        existing_docs = st.session_state.document_registry.list_documents()
        
        if existing_docs:
            st.success(f"📚 **{len(existing_docs)} document(s) stored**")
            st.caption("💾 Documents persist across restarts")

            st.divider()
            st.subheader("🔄 Load Stored Documents")

            # Get container from session state
            container = st.session_state.get('service_container')
            docs_loaded = (
                container is not None and
                hasattr(container.gateway_service, 'vectorstore') and container.gateway_service.vectorstore is not None and
                st.session_state.documents_processed
            )

            # Allow selecting a single document for Q&A
            st.divider()
            available_sources = sorted({doc.get('document_name', 'Unknown') for doc in existing_docs})
            selected_single = st.selectbox(
                "Select Document for Q&A",
                options=["📚 All Documents"] + available_sources,
                index=0,
                help="Select a specific document to query, or 'All Documents' to search across all uploaded documents."
            )
            selected_sources = [] if selected_single == "📚 All Documents" else [selected_single]
            
            # Auto-clear active_sources when "All Documents" is selected
            if selected_single == "📚 All Documents":
                if container:
                    container.gateway_service.active_sources = None  # Clear filter for all documents
                st.session_state.active_sources = []
            else:
                # Set active source when a specific document is selected
                if container:
                    container.gateway_service.active_sources = selected_sources
                st.session_state.active_sources = selected_sources

            # Buttons for per-document actions
            col_load, col_clear = st.columns(2)
            with col_load:
                if st.button("🔄 Load Selected Document", type="primary", use_container_width=True):
                    if not selected_sources:
                        st.warning("Please select one document to load.")
                    else:
                        with st.spinner(f"Loading {selected_sources[0]}..."):
                            try:
                                # Get vector store type from session state, existing RAG system, or config
                                if 'vector_store_choice' in st.session_state:
                                    current_vector_store = st.session_state.vector_store_choice.lower()
                                elif container and hasattr(container.gateway_service, 'vector_store_type'):
                                    current_vector_store = container.gateway_service.vector_store_type.lower()
                                else:
                                    # Fallback to config default
                                    current_vector_store = ARISConfig.VECTOR_STORE_TYPE.lower()
                                
                                current_embedding = embedding_model
                                current_chunk_size = ARISConfig.DEFAULT_CHUNK_SIZE
                                current_chunk_overlap = ARISConfig.DEFAULT_CHUNK_OVERLAP

                                # Get opensearch_domain and opensearch_index from multiple sources
                                opensearch_domain = None
                                opensearch_index = None

                                # Priority 1: Try to get from document metadata (if document was processed with OpenSearch)
                                if selected_sources:
                                    doc_name = selected_sources[0]
                                    # Find the document in the registry
                                    for doc in existing_docs:
                                        if doc.get('document_name') == doc_name:
                                            # Check if document was stored in OpenSearch
                                            if doc.get('storage_location') == 'opensearch_cloud' or \
                                               doc.get('vector_store_type', '').lower() == 'opensearch':
                                                opensearch_domain = doc.get('opensearch_domain')
                                                opensearch_index = doc.get('opensearch_index')
                                                break

                                # Priority 2: If not found in document, try existing RAG system
                                if not opensearch_domain and container:
                                    if hasattr(container.gateway_service, 'opensearch_domain'):
                                        opensearch_domain = container.gateway_service.opensearch_domain
                                    if hasattr(container.gateway_service, 'opensearch_index'):
                                        opensearch_index = container.gateway_service.opensearch_index

                                # Priority 3: If still not found and using OpenSearch, get from config
                                if not opensearch_domain and current_vector_store == 'opensearch':
                                    opensearch_config = ARISConfig.get_opensearch_config()
                                    opensearch_domain = opensearch_config.get('domain') or 'intelycx-waseem-os'
                                    opensearch_index = opensearch_config.get('index') or 'aris-rag-index'

                                # Priority 4: For FAISS, ensure they're None (not needed)
                                if current_vector_store == 'faiss':
                                    opensearch_domain = None
                                    opensearch_index = None

                                # Validate OpenSearch configuration if needed
                                if current_vector_store == 'opensearch' and not opensearch_domain:
                                    st.error("❌ OpenSearch domain not found. Please ensure the document was processed with OpenSearch or configure OpenSearch settings.")
                                    st.stop()

                                # Use Unified Service Container
                                if 'service_container' not in st.session_state:
                                    st.session_state.service_container = ServiceContainer()
                                
                                # Compatibility bindings
                                container = st.session_state.service_container
                                st.session_state.document_processor = container.document_processor
                                
                                # Set active sources for filtering
                                container.gateway_service.active_sources = selected_sources
                                
                                vectorstore_base_path = ARISConfig.VECTORSTORE_PATH
                                
                                # For FAISS, ensure we're using the correct path
                                if current_vector_store == "faiss":
                                    # Check if vectorstore exists
                                    model_specific_path = ARISConfig.get_vectorstore_path(current_embedding)
                                    if not os.path.exists(model_specific_path) and not os.path.exists(vectorstore_base_path):
                                        st.error(f"❌ Vectorstore not found at: {model_specific_path}\n\n"
                                                f"Please process and save documents first.")
                                        st.stop()
                                
                                # Enforce single-document load
                                container.gateway_service.active_sources = selected_sources
                                
                                # Load the selected document
                                result = container.gateway_service.load_selected_documents(
                                    document_names=selected_sources[:1],
                                    path=vectorstore_base_path  # Pass base path, method handles model-specific
                                )

                                if result.get("loaded"):
                                    st.session_state.vectorstore_loaded = True
                                    st.session_state.documents_processed = True
                                    st.session_state.active_sources = selected_sources
                                    st.session_state.active_loaded_docs = selected_sources
                                    st.success(f"✅ {result.get('message', 'Loaded selected document.')}")
                                    chunks_loaded = result.get("chunks_loaded", 0)
                                    docs_loaded = result.get("docs_loaded", 0)
                                    if chunks_loaded:
                                        st.caption(f"📊 {chunks_loaded:,} chunks from {docs_loaded} document(s) ready for Q&A")
                                    st.rerun()
                                else:
                                    error_msg = result.get("message", "Could not load selected documents.")
                                    st.error(f"❌ {error_msg}")
                                    # Show helpful debugging info
                                    with st.expander("🔍 Troubleshooting", expanded=False):
                                        st.write(f"**Document name:** {selected_sources[0]}")
                                        st.write(f"**Vectorstore path:** {vectorstore_base_path}")
                                        st.write(f"**Model-specific path:** {ARISConfig.get_vectorstore_path(current_embedding)}")
                                        st.write(f"**Vectorstore exists:** {os.path.exists(ARISConfig.get_vectorstore_path(current_embedding))}")
                                        # Show available document sources if possible
                                        try:
                                            container = st.session_state.get('service_container')
                                            if container and hasattr(container.gateway_service, 'vectorstore'):
                                                st.write("**Note:** Make sure the document name matches exactly what's stored in the vectorstore.")
                                        except:
                                            pass
                            except Exception as e:
                                st.error(f"❌ Error loading selected documents: {e}")
                                import traceback
                                with st.expander("🔍 Error Details", expanded=False):
                                    st.code(traceback.format_exc())

            with col_clear:
                if st.button("🧹 Clear Loaded Selection", use_container_width=True):
                    st.session_state.active_sources = []
                    st.session_state.active_loaded_docs = []
                    container = st.session_state.get('service_container')
                    if container:
                        container.gateway_service.active_sources = []
                    st.info("Selection cleared. Choose documents and load again to start Q&A.")

            # Status of currently loaded docs - Enhanced with active document indicator
            container = st.session_state.get('service_container')
            if container and container.gateway_service.active_sources:
                active_docs = container.gateway_service.active_sources
                if active_docs:
                    st.info(f"📄 **Active Document:** {', '.join(active_docs)}\n\n"
                            f"Queries will only search within this document. Select '📚 All Documents' to search all documents.")
            elif st.session_state.active_loaded_docs:
                st.success(f"✅ Loaded for Q&A: {', '.join(st.session_state.active_loaded_docs)}")
                try:
                    vs = container.gateway_service.vectorstore if container else None
                    if vs and hasattr(vs, 'index') and hasattr(vs.index, 'ntotal'):
                        st.caption(f"📊 {vs.index.ntotal:,} chunks loaded")
                except Exception:
                    pass
            elif container and hasattr(container.gateway_service, 'vectorstore') and container.gateway_service.vectorstore:
                # Show status when all documents are active (no filter)
                st.info("📚 **All Documents Active**\n\n"
                        "Queries will search across all uploaded documents.")

            # Document review expander
            with st.expander("📖 Review Stored Documents", expanded=False):
                # Sort by creation date (newest first)
                sorted_docs = sorted(
                    existing_docs, 
                    key=lambda x: str(x.get('created_at', '')), 
                    reverse=True
                )
                
                for idx, doc in enumerate(sorted_docs):
                    doc_name = doc.get('document_name', 'Unknown')
                    doc_id = doc.get('document_id', 'N/A')
                    chunks = doc.get('chunks_created', 0)
                    tokens = doc.get('tokens_extracted', 0)
                    parser = doc.get('parser_used', 'unknown')
                    created = str(doc.get('created_at', 'N/A'))
                    pages = doc.get('pages', 'N/A')
                    status = doc.get('status', 'unknown')
                    try:
                        processing_time = float(doc.get('processing_time', 0))
                    except (TypeError, ValueError):
                        processing_time = 0.0
                    
                    # Format date
                    if created and len(created) > 10:
                        date_str = created[:10]  # YYYY-MM-DD
                        time_str = created[11:19] if len(created) > 19 else ""
                        display_date = f"{date_str} {time_str}".strip()
                    else:
                        display_date = created
                    
                    # Document card
                    with st.container():
                        st.markdown(f"**📄 {doc_name}**")
                        
                        # Status badge
                        badge_class = "badge-success" if status == 'success' else "badge-error" if status == 'failed' else "badge-warning"
                        st.markdown(f'<span class="badge {badge_class}">{status.upper()}</span>', unsafe_allow_html=True)
                        
                        # Document stats in columns
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption(f"📊 {chunks} chunks")
                            st.caption(f"🔤 {tokens:,} tokens")
                        with col2:
                            st.caption(f"📑 {pages} pages")
                            if processing_time > 0:
                                st.caption(f"⏱️ {processing_time:.1f}s")
                        
                        # Metadata
                        st.caption(f"🔧 Parser: {parser}")
                        st.caption(f"📅 Added: {display_date}")
                        st.caption(f"🆔 ID: `{doc_id[:12]}...`")
                        
                        # Storage location
                        storage_location = doc.get('storage_location', 'local_faiss')
                        vector_store_type = doc.get('vector_store_type', 'faiss')
                        if storage_location == 'opensearch_cloud' or vector_store_type.lower() == 'opensearch':
                            opensearch_domain = doc.get('opensearch_domain', 'N/A')
                            opensearch_index = doc.get('opensearch_index', 'N/A')
                            st.caption(f"☁️ Storage: OpenSearch Cloud (Domain: {opensearch_domain}, Index: {opensearch_index})")
                        else:
                            st.caption(f"💾 Storage: Local FAISS")
                        
                        # Extraction quality
                        extraction_pct = doc.get('extraction_percentage', 0)
                        if extraction_pct > 0:
                            st.progress(extraction_pct, text=f"Extraction: {extraction_pct*100:.1f}%")
                        
                        if idx < len(sorted_docs) - 1:
                            st.divider()
            
            # Storage info
            with st.expander("💾 Storage Information", expanded=False):
                # Determine current vector store type
                vector_store_type = 'faiss'
                opensearch_domain = None
                opensearch_index = None
                container = st.session_state.get('service_container')
                if container:
                    vector_store_type = getattr(container.gateway_service, 'vector_store_type', 'faiss')
                    if vector_store_type.lower() == 'opensearch':
                        opensearch_domain = getattr(container.gateway_service, 'opensearch_domain', None)
                        opensearch_index = getattr(container.gateway_service, 'opensearch_index', None)
                
                if vector_store_type.lower() == 'opensearch':
                    st.info("""
                    **Long-term Storage:**
                    - ✅ Document metadata saved to: `storage/document_registry.json`
                    - ✅ Vectorstore embeddings saved to: OpenSearch Cloud
                    - ✅ Documents persist across server restarts
                    - ✅ Auto-loaded on startup
                    - ✅ OpenSearch provides cloud-based persistence
                    """)
                    
                    # Show storage paths
                    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
                    
                    st.caption(f"📁 Registry: `{registry_path}`")
                    st.caption(f"☁️ Vectorstore: OpenSearch Cloud")
                    if opensearch_domain:
                        st.caption(f"🌐 OpenSearch Domain: `{opensearch_domain}`")
                    if opensearch_index:
                        st.caption(f"📇 OpenSearch Index: `{opensearch_index}`")
                else:
                    st.info("""
                    **Long-term Storage:**
                    - ✅ Document metadata saved to: `storage/document_registry.json`
                    - ✅ Vectorstore embeddings saved to: `vectorstore/`
                    - ✅ Documents persist across server restarts
                    - ✅ Auto-loaded on startup
                    """)
                    
                    # Show storage paths
                    registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
                    vectorstore_path = ARISConfig.get_vectorstore_path()
                    
                    st.caption(f"📁 Registry: `{registry_path}`")
                    st.caption(f"📁 Vectorstore: `{vectorstore_path}`")
                
                # Sync status
                sync_status = st.session_state.document_registry.get_sync_status()
                st.caption(f"📊 Total documents: {sync_status.get('total_documents', 0)}")
                if sync_status.get('last_update'):
                    st.caption(f"🕒 Last update: {sync_status['last_update'][:19]}")
        else:
            st.info("📭 No documents stored yet")
            st.caption("Upload and process documents to see them here")
    else:
        st.warning("⚠️ Document registry not initialized")
    
    # Chunking Strategy selection
    st.divider()
    st.header("✂️ Chunking Strategy")
    
    chunking_strategies = get_all_strategies()
    strategy_options = ["Precise", "Balanced", "Comprehensive", "Custom"]
    
    # Use shared config default for chunking strategy
    strategy_map = {'precise': 0, 'balanced': 1, 'comprehensive': 2, 'custom': 3}
    default_strategy_index = strategy_map.get(ARISConfig.CHUNKING_STRATEGY.lower(), 1)
    chunking_strategy = st.selectbox(
        "Choose Chunking Strategy:",
        strategy_options,
        index=default_strategy_index,
        help="Select how documents should be split into chunks. "
             "Precise: Small chunks for exact matches. "
             "Balanced: Medium chunks (recommended). "
             "Comprehensive: Large chunks with more context. "
             "Custom: Set your own chunk size and overlap."
    )
    
    # Use defaults optimized for large documents
    chunk_size = ARISConfig.DEFAULT_CHUNK_SIZE
    chunk_overlap = ARISConfig.DEFAULT_CHUNK_OVERLAP
    
    if chunking_strategy == "Custom":
        st.subheader("Custom Chunking Parameters")
        chunk_size = st.number_input(
            "Chunk Size (tokens):",
            min_value=1,
            value=ARISConfig.DEFAULT_CHUNK_SIZE,
            step=1,
            help="Maximum number of tokens per chunk. Set any value you want. Smaller = more precise, Larger = more context."
        )
        chunk_overlap = st.number_input(
            "Chunk Overlap (tokens):",
            min_value=0,
            value=ARISConfig.DEFAULT_CHUNK_OVERLAP,
            step=1,
            help="Number of tokens to overlap between chunks. Can be any value (even >= chunk_size). Helps maintain context continuity."
        )
        
        # Warn about unusual configurations but don't block
        if chunk_overlap >= chunk_size:
            st.warning(
                f"⚠️ **Warning:** Overlap ({chunk_overlap}) is >= chunk size ({chunk_size}). "
                f"This may cause excessive overlap. Consider reducing overlap to < {chunk_size}."
            )
        elif chunk_size < 50:
            st.warning(
                f"⚠️ **Warning:** Very small chunk size ({chunk_size} tokens). "
                f"Chunks smaller than 50 tokens may lose context. Consider using at least 50-100 tokens."
            )
        elif chunk_size > 5000:
            st.warning(
                f"⚠️ **Warning:** Very large chunk size ({chunk_size} tokens). "
                f"Chunks larger than 5000 tokens may impact retrieval precision and embedding quality."
            )
    else:
        # Get parameters from preset
        strategy_key = chunking_strategy.lower()
        chunk_size, chunk_overlap = get_chunking_params(strategy_key)
        
        # Show strategy info
        strategy_info = chunking_strategies[strategy_key]
        with st.expander(f"ℹ️ {strategy_info['name']} Strategy Details", expanded=False):
            st.write(f"**Chunk Size:** {strategy_info['chunk_size']} tokens")
            st.write(f"**Overlap:** {strategy_info['chunk_overlap']} tokens")
            st.write(f"**Description:** {strategy_info['description']}")
            st.write(f"**Use Case:** {strategy_info['use_case']}")
    
    # Vector Store selection (use shared config default)
    st.divider()
    st.header("💾 Vector Store Settings")
    default_vector_store = "OpenSearch" if ARISConfig.VECTOR_STORE_TYPE.lower() == "opensearch" else "FAISS"
    vector_store_choice = st.radio(
        "Choose Vector Store:",
        ["FAISS", "OpenSearch"],
        index=1 if ARISConfig.VECTOR_STORE_TYPE.lower() == "opensearch" else 0,
        help="FAISS: Local storage, fast, no cloud required. "
             "OpenSearch: Cloud storage, scalable, requires AWS OpenSearch domain."
    )
    # Store in session state for use in Document Library section
    st.session_state.vector_store_choice = vector_store_choice
    
    # OpenSearch configuration is handled automatically - no user input needed
    # Domain and index names are auto-configured from environment/settings
    # Per-document indexes are created automatically (aris-doc-{document_id})
    opensearch_config = ARISConfig.get_opensearch_config()
    opensearch_domain = opensearch_config.get('domain') or 'intelycx-waseem-os'
    opensearch_index = opensearch_config.get('index') or 'aris-rag-index'
    
    if vector_store_choice == "OpenSearch":
        # Show auto-configured settings (read-only info)
        st.success(f"☁️ **OpenSearch Auto-Configured**")
        st.caption(f"Domain: `{opensearch_domain}` | Default Index: `{opensearch_index}`")
        st.caption("📇 Each document gets its own index automatically (e.g., `aris-doc-policy-manual`)")
        
        # Check if credentials are available
        from dotenv import load_dotenv
        load_dotenv()
        if not os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') or not os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'):
            st.error("⚠️ OpenSearch credentials not found in .env file. Please add AWS_OPENSEARCH_ACCESS_KEY_ID and AWS_OPENSEARCH_SECRET_ACCESS_KEY")
    else:
        st.info("💡 FAISS stores data locally in the 'vectorstore/' directory")
    
    st.divider()
    
    # Document upload
    st.markdown("### 📄 Upload Documents")
    
    # Document Language Selector for Ingestion (Enhanced multilingual support)
    # Language options with friendly names
    language_options = {
        "eng": "🇬🇧 English",
        "spa": "🇪🇸 Spanish",
        "fra": "🇫🇷 French",
        "deu": "🇩🇪 German",
        "ita": "🇮🇹 Italian",
        "por": "🇵🇹 Portuguese",
        "nld": "🇳🇱 Dutch",
        "rus": "🇷🇺 Russian",
        "ukr": "🇺🇦 Ukrainian",
        "pol": "🇵🇱 Polish",
        "zho": "🇨🇳 Chinese (Simplified)",
        "jpn": "🇯🇵 Japanese",
        "kor": "🇰🇷 Korean",
        "ara": "🇸🇦 Arabic",
        "heb": "🇮🇱 Hebrew",
        "hin": "🇮🇳 Hindi",
        "tha": "🇹🇭 Thai",
        "vie": "🇻🇳 Vietnamese",
        "tur": "🇹🇷 Turkish",
        "ell": "🇬🇷 Greek",
        "ces": "🇨🇿 Czech",
        "auto": "🔍 Auto-detect",
    }
    
    ingestion_language = st.selectbox(
        "Document Language:",
        options=list(language_options.keys()),
        format_func=lambda x: language_options.get(x, x),
        index=0,
        key="document_language_selectbox",
        help="Language of the documents being uploaded. Used for language-aware OCR, chunking, and indexing. "
             "Select 'Auto-detect' to let the system detect the language automatically. "
             "⚠️ **For OCRmyPDF:** This automatically sets the OCR language. Change this to update OCR settings above."
    )
    
    # Store in session state for OCR language sync (used by OCR settings above)
    previous_lang = st.session_state.get('last_document_language', 'eng')
    st.session_state['last_document_language'] = ingestion_language
    
    # If language changed and OCRmyPDF is selected, trigger rerun to update OCR languages
    if previous_lang != ingestion_language and parser_choice == "OCRmyPDF":
        # Clear OCR languages to force update
        if 'ocr_languages_value' in st.session_state:
            del st.session_state['ocr_languages_value']
        # Note: We don't rerun here to avoid infinite loops, but the OCR settings will update on next render
    
    # Convert 'auto' to 'eng' for backend processing (auto-detection happens in processor)
    if ingestion_language == "auto":
        ingestion_language = "eng"  # Default to English, processor will auto-detect
    
    # Force update option for re-processing existing documents
    force_update = st.checkbox(
        "🔄 Force Update (Re-process even if document exists)",
        value=False,
        help="If checked, documents will be re-processed even if they already exist with identical content. "
             "This is useful when you want to re-index with a different parser or update the embeddings."
    )
    
    uploaded_files = st.file_uploader(
        "Choose files",
        type=['pdf', 'txt', 'docx', 'doc'],
        accept_multiple_files=True,
        help="Upload PDF, TXT, or DOCX files"
    )
    
    # Store processing parameters in session state for continuation after rerun
    process_key = "pending_processing"
    
    # Check if we should continue processing (after user makes index choice)
    should_process = False
    if process_key in st.session_state and st.session_state[process_key] is not None:
        should_process = True
        params = st.session_state[process_key]
    
    if st.button("Process Documents", type="primary"):
        if uploaded_files:
            # Read file contents immediately (before storing in session state)
            # Streamlit file objects become invalid after rerun, so we need to read them now
            files_data = []
            for uploaded_file in uploaded_files:
                file_content = uploaded_file.read()
                files_data.append({
                    'name': uploaded_file.name,
                    'content': file_content,
                    'type': uploaded_file.type
                })
            
            # Store processing parameters in session state (with file contents, not file objects)
            # Use explicit document language from upload section
            document_language = ingestion_language
            st.session_state[process_key] = {
                'files_data': files_data,  # Store file contents, not file objects
                'use_cerebras': use_cerebras,
                'parser_preference': parser_preference,
                'embedding_model': embedding_model,
                'openai_model': openai_model,
                'cerebras_model': cerebras_model,
                'vector_store_type': vector_store_choice.lower(),
                'opensearch_domain': opensearch_domain,
                'opensearch_index': opensearch_index,
                'chunk_size': chunk_size,
                'chunk_overlap': chunk_overlap,
                'document_language': document_language,
                'force_update': force_update  # Pass force update flag
            }
            should_process = True
            params = st.session_state[process_key]
        else:
            st.warning("Please upload at least one document")
    
    # Continue processing if there's pending processing
    if should_process:
        # Convert stored file data back to format expected by process_uploaded_files
        # Create mock file objects from stored data
        class MockUploadedFile:
            def __init__(self, name, content, content_type):
                self.name = name
                self._content = content
                self.type = content_type
            def read(self):
                return self._content
        
        mock_uploaded_files = [
            MockUploadedFile(f['name'], f['content'], f.get('type', 'application/pdf'))
            for f in params['files_data']
        ]
        
        # Process documents (don't clear the flag yet - let process_uploaded_files handle it)
        result = process_uploaded_files(
            mock_uploaded_files, params['use_cerebras'], params['parser_preference'],
            params['embedding_model'], params['openai_model'], params['cerebras_model'],
            params['vector_store_type'], params['opensearch_domain'], params['opensearch_index'],
            params['chunk_size'], params['chunk_overlap'],
            params.get('document_language', 'eng'),  # Get document_language from params, default to 'eng'
            params.get('force_update', False)  # Get force_update from params, default to False
        )
        # Only clear the flag if processing completed successfully (no user interaction needed)
        # If user interaction is needed (duplicate index), the flag stays so processing can continue after choice
        if result is not False:
            # Check if any files are still waiting for user choice
            has_pending_choice = False
            if 'files_data' in params:
                for file_data in params['files_data']:
                    file_name = file_data['name']
                    choice_key = f"index_choice_{file_name}"
                    if choice_key in st.session_state and st.session_state[choice_key] is None:
                        has_pending_choice = True
                        break
            
            # Only clear if no pending choices
            if not has_pending_choice:
                del st.session_state[process_key]
                # Ensure container and state are preserved before rerun
                if 'service_container' not in st.session_state:
                    if st.session_state.documents_processed:
                        # Re-initialize container if missing but documents were processed
                        st.session_state.service_container = ServiceContainer()
                        # Restore active sources if they were set
                        if st.session_state.active_sources:
                            st.session_state.service_container.gateway_service.active_sources = st.session_state.active_sources
                    else:
                        # Initialize container even if documents not processed yet (might be needed)
                        st.session_state.service_container = ServiceContainer()
                # Force UI refresh to show completion and clear processing messages
                st.rerun()
    
    st.divider()
    
    # Comprehensive Metrics Dashboard
    st.header("📊 R&D Metrics & Analytics")
    
    # Ensure container is available if documents were processed
    container = st.session_state.get('service_container')
    if st.session_state.documents_processed and not container:
        # Re-initialize container if documents were processed but container is missing
        try:
            st.session_state.service_container = ServiceContainer()
            container = st.session_state.service_container
        except Exception as e:
            logger.warning(f"Could not re-initialize container: {e}")
    
    if st.session_state.documents_processed and container:
        # Get all metrics (sync version for Streamlit UI)
        if hasattr(container.gateway_service, 'get_all_metrics'):
            try:
                all_metrics = container.gateway_service.get_all_metrics()
            except Exception as e:
                logger.warning(f"Could not fetch metrics from gateway: {e}")
                all_metrics = st.session_state.metrics_collector.get_all_metrics() if hasattr(st.session_state, 'metrics_collector') else {}
        else:
            all_metrics = st.session_state.metrics_collector.get_all_metrics() if hasattr(st.session_state, 'metrics_collector') else {}
            
        processing_stats = all_metrics.get('processing', {})
        query_stats = all_metrics.get('queries', {})
        parser_comparison = all_metrics.get('parser_comparison', {})
        
        # Model Information
        st.subheader("🤖 Current Models")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.info(f"**Embedding:**\n{container.gateway_service.embedding_model}")
        with col2:
            if container.gateway_service.use_cerebras:
                st.info(f"**LLM:**\n{container.gateway_service.cerebras_model}")
            else:
                st.info(f"**LLM:**\n{container.gateway_service.openai_model}")
        with col3:
            api_name = "Cerebras" if container.gateway_service.use_cerebras else "OpenAI"
            st.info(f"**API:**\n{api_name}")
        with col4:
            vector_store_type = getattr(container.gateway_service, 'vector_store_type', 'faiss')
            store_display = vector_store_type.upper()
            if vector_store_type == "opensearch":
                domain = getattr(container.gateway_service, 'opensearch_domain', 'N/A')
                store_display += f"\n({domain})"
            st.info(f"**Vector Store:**\n{store_display}")
        with col5:
            chunk_size = getattr(container.gateway_service, 'chunk_size', ARISConfig.DEFAULT_CHUNK_SIZE)
            chunk_overlap = getattr(container.gateway_service, 'chunk_overlap', ARISConfig.DEFAULT_CHUNK_OVERLAP)
            st.info(f"**Chunking:**\n{chunk_size} tokens\n({chunk_overlap} overlap)")
        
        # Basic Stats
        st.subheader("📈 Overview")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
             st.markdown(get_glass_card("Documents", processing_stats.get('total_documents', 0)), unsafe_allow_html=True)
        with col2:
             st.markdown(get_glass_card("Chunks", processing_stats.get('total_chunks', 0)), unsafe_allow_html=True)
        with col3:
             st.markdown(get_glass_card("Total Tokens", f"{processing_stats.get('total_tokens', 0):,}"), unsafe_allow_html=True)
        with col4:
             st.markdown(get_glass_card("Queries", query_stats.get('total_queries', 0)), unsafe_allow_html=True)
        
        # Performance Metrics
        st.subheader("⚡ Performance")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Avg Processing Time",
                f"{processing_stats.get('avg_processing_time', 0):.2f}s"
            )
        with col2:
            st.metric(
                "Avg Response Time",
                f"{query_stats.get('avg_response_time', 0):.2f}s"
            )
        with col3:
            st.metric(
                "Success Rate",
                f"{processing_stats.get('success_rate', 0)*100:.1f}%"
            )
        with col4:
            st.metric(
                "Query Success Rate",
                f"{query_stats.get('success_rate', 0)*100:.1f}%"
            )
        
        # Parser Comparison
        if parser_comparison:
            st.subheader("🔧 Parser Performance")
            parser_data = []
            for parser, stats in parser_comparison.items():
                parser_data.append({
                    'Parser': parser,
                    'Usage': stats.get('usage_count', 0),
                    'Success Rate': f"{stats.get('success_rate', 0)*100:.1f}%",
                    'Avg Time (s)': f"{stats.get('avg_processing_time', 0):.2f}",
                    'Avg Tokens': f"{int(stats.get('avg_tokens_per_doc', 0)):,}",
                    'Avg Chunks': f"{int(stats.get('avg_chunks_per_doc', 0))}",
                    'Confidence': f"{stats.get('avg_confidence', 0):.2f}",
                    'Extraction %': f"{stats.get('avg_extraction_percentage', 0):.1f}%"
                })
            if parser_data:
                st.dataframe(parser_data, width='stretch')
        
        # Quality Metrics
        st.subheader("🎯 Quality Metrics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Avg Extraction %",
                f"{processing_stats.get('avg_extraction_percentage', 0):.1f}%"
            )
        with col2:
            st.metric(
                "Avg Confidence",
                f"{processing_stats.get('avg_confidence', 0):.2f}"
            )
        with col3:
            st.metric(
                "Avg Chunks/Doc",
                f"{processing_stats.get('avg_chunks_per_document', 0):.1f}"
            )
        with col4:
            st.metric(
                "Avg Tokens/Doc",
                f"{int(processing_stats.get('avg_tokens_per_document', 0)):,}"
            )
        
        # Query Analytics
        if query_stats.get('total_queries', 0) > 0:
            st.subheader("💬 Query Analytics")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric(
                    "Avg Answer Length",
                    f"{int(query_stats.get('avg_answer_length', 0))} chars"
                )
            with col2:
                st.metric(
                    "Avg Chunks/Query",
                    f"{query_stats.get('avg_chunks_per_query', 0):.1f}"
                )
            with col3:
                st.metric(
                    "Avg Context Tokens",
                    f"{int(query_stats.get('avg_context_tokens', 0)):,}"
                )
            with col4:
                st.metric(
                    "Avg Response Tokens",
                    f"{int(query_stats.get('avg_response_tokens', 0)):,}"
                )
            col5, col6 = st.columns(2)
            with col5:
                st.metric(
                    "Total Query Tokens",
                    f"{int(query_stats.get('total_query_tokens', 0)):,}"
                )
            with col6:
                api_usage = query_stats.get('api_usage', {})
                if api_usage:
                    st.write("**API Usage:**")
                    for api, count in api_usage.items():
                        st.write(f"- {api.capitalize()}: {count}")
        
        # Token Analysis Section
        if container and hasattr(container.gateway_service, 'vectorstore') and container.gateway_service.vectorstore:
            st.subheader("🔢 Token Analysis")
            chunk_stats = container.gateway_service.get_chunk_token_stats()
            
            if chunk_stats['total_chunks'] > 0:
                # Show configured vs actual chunk sizes
                configured_size = chunk_stats.get('configured_chunk_size', 384)
                configured_overlap = chunk_stats.get('configured_chunk_overlap', 75)
                actual_avg = chunk_stats['avg_tokens_per_chunk']
                actual_max = chunk_stats['max_tokens_per_chunk']
                
                # Calculate utilization percentage
                utilization = (actual_avg / configured_size * 100) if configured_size > 0 else 0
                
                st.info(
                    f"📋 **Chunking Settings:** Maximum chunk size = {configured_size} tokens "
                    f"(overlap: {configured_overlap}) | "
                    f"**Actual Results:** Average = {actual_avg:.1f} tokens/chunk "
                    f"({utilization:.1f}% of max), Max = {actual_max} tokens"
                )
                
                if utilization < 50:
                    st.warning(
                        f"💡 **Note:** Your chunks are using only {utilization:.1f}% of the configured maximum size. "
                        f"This is normal - chunks are sized based on sentence boundaries and document structure. "
                        f"The configured size ({configured_size}) is a maximum limit, not a target."
                )
                
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Total Chunks", f"{chunk_stats['total_chunks']:,}")
                with col2:
                    st.metric(
                        "Avg Tokens/Chunk",
                        f"{chunk_stats['avg_tokens_per_chunk']:.1f}",
                        help="Actual average tokens per chunk (may be less than configured max)"
                    )
                with col3:
                    st.metric(
                        "Min Tokens/Chunk",
                        f"{int(chunk_stats['min_tokens_per_chunk'])}"
                    )
                with col4:
                    st.metric(
                        "Max Tokens/Chunk",
                        f"{int(chunk_stats['max_tokens_per_chunk'])}"
                    )
                with col5:
                    st.metric(
                        "Config Max Size",
                        f"{configured_size}",
                        help="Configured maximum chunk size"
                    )
                
                # Token distribution histogram
                if chunk_stats.get('chunk_token_counts'):
                    # Create histogram data
                    token_counts = chunk_stats['chunk_token_counts']
                    df_tokens = pd.DataFrame({'Tokens per Chunk': token_counts})
                    
                    st.write("**Token Distribution:**")
                    st.bar_chart(df_tokens, x=None, y='Tokens per Chunk', height=300)
                    
                    # Show distribution statistics
                    with st.expander("📊 Detailed Token Statistics"):
                        st.write(f"**Total Chunks:** {len(token_counts):,}")
                        st.write(f"**Average:** {np.mean(token_counts):.1f} tokens")
                        st.write(f"**Median:** {np.median(token_counts):.1f} tokens")
                        st.write(f"**Standard Deviation:** {np.std(token_counts):.1f} tokens")
                        st.write(f"**25th Percentile:** {np.percentile(token_counts, 25):.1f} tokens")
                        st.write(f"**75th Percentile:** {np.percentile(token_counts, 75):.1f} tokens")
                        
                        # Show token count ranges (dynamic based on configured chunk size)
                        configured_max = chunk_stats.get('configured_chunk_size', 384)
                        range_size = max(100, configured_max // 5)  # 5 ranges
                        ranges = {}
                        for i in range(5):
                            start = i * range_size
                            end = (i + 1) * range_size
                            if i == 4:
                                ranges[f'{start}+'] = sum(1 for t in token_counts if t >= start)
                            else:
                                ranges[f'{start}-{end}'] = sum(1 for t in token_counts if start <= t < end)
                        st.write("**Token Count Ranges:**")
                        range_df = pd.DataFrame(list(ranges.items()), columns=['Range', 'Count'])
                        st.dataframe(range_df, width='stretch')
            else:
                st.info("No chunk token statistics available yet.")
        
        # File Type Statistics
        file_type_stats = processing_stats.get('file_type_statistics', {})
        if file_type_stats:
            st.subheader("📁 File Type Statistics")
            file_data = []
            for file_type, stats in file_type_stats.items():
                file_data.append({
                    'Type': file_type.upper(),
                    'Count': stats.get('count', 0),
                    'Total Size (MB)': f"{stats.get('total_size', 0) / (1024*1024):.2f}",
                    'Total Time (s)': f"{stats.get('total_time', 0):.2f}",
                    'Total Tokens': f"{stats.get('total_tokens', 0):,}"
                })
            if file_data:
                st.dataframe(file_data, width='stretch')
        
        # Error Summary
        error_summary = all_metrics.get('error_summary', {})
        if error_summary.get('total_errors', 0) > 0:
            st.subheader("⚠️ Error Summary")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Errors", error_summary.get('total_errors', 0))
            with col2:
                st.metric("Processing Errors", error_summary.get('processing_errors', 0))
        
        # Detailed Processing Results
        if st.session_state.processing_results:
            with st.expander("📋 Detailed Processing Results"):
                for result in st.session_state.processing_results:
                    if result.status == 'success':
                        st.write(f"✅ **{result.document_name}**")
                        st.write(f"   - Parser: {result.parser_used}")
                        st.write(f"   - Chunks: {result.chunks_created}")
                        st.write(f"   - Tokens: {result.tokens_extracted:,}")
                        st.write(f"   - Time: {result.processing_time:.2f}s")
                        st.write(f"   - Extraction: {result.extraction_percentage:.1f}%")
                        if result.images_detected:
                            st.write("   - ⚠️ Images detected")
                    else:
                        st.write(f"❌ **{result.document_name}**: {result.error}")
        
        # Export Metrics
        st.subheader("💾 Export Metrics")
        metrics_json = json.dumps(st.session_state.metrics_collector.export_to_dict(), indent=2)
        st.download_button(
            label="Download Metrics (JSON)",
            data=metrics_json,
            file_name="rag_metrics.json",
            mime="application/json"
        )
        
        # Sync Status Section
        st.divider()
        st.subheader("🔄 Synchronization Status")
        
        container = st.session_state.get('service_container')
        if container and hasattr(container.gateway_service, 'get_sync_status_sync'):
            try:
                sync_status = container.gateway_service.get_sync_status_sync()
                
                # Check consistency
                gw_docs = sync_status.get('gateway', {}).get('document_count', 0)
                ing_docs = sync_status.get('ingestion', {}).get('status', {}).get('total_documents', gw_docs)
                ret_docs = sync_status.get('retrieval', {}).get('status', {}).get('total_documents', gw_docs)
                
                is_synced = (gw_docs == ing_docs == ret_docs)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Gateway Docs", gw_docs)
                with col2:
                    st.metric("Ingestion Docs", ing_docs)
                    if ing_docs != gw_docs:
                        st.warning("⚠️ Ingestion registry out of sync")
                with col3:
                    st.metric("Retrieval Docs", ret_docs)
                    if ret_docs != gw_docs:
                        st.warning("⚠️ Retrieval registry out of sync")
                
                if is_synced:
                    st.success("✅ All services fully synchronized")
                else:
                    st.warning("⚠️ Synchronization issues detected between services")
                
                # Manual sync button
                if st.button("🔄 Force Global Sync", help="Trigger a manual synchronization across all microservices"):
                    with st.spinner("Syncing services..."):
                        result = container.gateway_service.force_sync_sync()
                        if result.get("success"):
                            # Also reload local registry in UI
                            if hasattr(st.session_state.document_registry, 'reload_from_disk'):
                                st.session_state.document_registry.reload_from_disk()
                            st.success("✅ Global synchronization triggered successfully")
                            st.rerun()
                        else:
                            st.error(f"❌ Sync failed: {result.get('error')}")
                
                # Detailed status in expander
                with st.expander("Detailed Service Status"):
                    st.json(sync_status)
            except Exception as e:
                st.error(f"Error fetching sync status: {e}")
        else:
            # Fallback for old/uninitialized container
            st.info("ℹ️ Sync status only available in microservices mode")
    else:
        st.info("⏳ No documents processed yet. Upload and process documents to see metrics.")
    
    # Persistent Citations Section
    st.divider()
    st.header("📎 Latest Citations")
    
    if st.session_state.citations_history and len(st.session_state.citations_history) > 0:
        # Show the most recent citations
        latest = st.session_state.citations_history[-1]
        citations = latest.get('citations', [])
        
        if citations and len(citations) > 0:
            st.info(f"**{len(citations)} citation(s) from last query:**")
            st.caption(f"Q: {latest.get('question', 'N/A')[:50]}...")
            
            # Show citations in sidebar (compact view)
            for citation in citations[:5]:  # Show first 5 citations
                citation_id = citation.get('id', '?')
                source_name = citation.get('source', 'Unknown')
                page = citation.get('page') or 1
                source_location = citation.get('source_location', '')
                
                with st.expander(f"[{citation_id}] {source_name.split('/')[-1][:30]}...", expanded=False):
                    # Always show page number - page is guaranteed to be >= 1
                    st.success(f"📍 Page {page}")
                    if source_location:
                        st.caption(f"Location: {source_location}")
                    
                    snippet = citation.get('snippet', citation.get('full_text', ''))
                    if snippet:
                        st.text_area(
                            "Source text:",
                            snippet[:200] + "..." if len(snippet) > 200 else snippet,
                            height=80,
                            key=f"sidebar_citation_{citation_id}_{len(st.session_state.citations_history)}",
                            label_visibility="collapsed"
                        )
            
            if len(citations) > 5:
                st.caption(f"... and {len(citations) - 5} more citations")
            
            # Button to clear citations
            if st.button("🗑️ Clear Citations", use_container_width=True, key="clear_citations"):
                st.session_state.citations_history = []
                st.rerun()
        else:
            st.info("No citations available for the last query.")
    else:
        st.info("👆 Ask a question to see citations here.")
    
    # Clear button
    if st.button("Clear All", type="secondary"):
        if 'service_container' in st.session_state:
            del st.session_state.service_container
        st.session_state.documents_processed = False
        st.session_state.chat_history = []
        st.session_state.citations_history = []
        st.session_state.processing_results = []
        st.session_state.document_processor = None
        st.session_state.metrics_collector.clear()
        st.rerun()

# Main content area
# Ensure container is available if documents were processed
container = st.session_state.get('service_container')
if st.session_state.documents_processed and not container:
    # Re-initialize container if documents were processed but container is missing
    try:
        st.session_state.service_container = ServiceContainer()
        container = st.session_state.service_container
        # Restore active sources if they were set
        if st.session_state.active_sources:
            container.gateway_service.active_sources = st.session_state.active_sources
            # For OpenSearch, reload the selected documents
            if getattr(container.gateway_service, 'vector_store_type', '').lower() == 'opensearch':
                try:
                    container.gateway_service.load_selected_documents(
                        document_names=st.session_state.active_sources,
                        path=ARISConfig.VECTORSTORE_PATH
                    )
                except Exception as e:
                    logger.warning(f"Could not reload OpenSearch documents: {e}")
        # Try to reload vectorstore if it was saved (FAISS only)
        elif st.session_state.vectorstore_loaded:
            try:
                vectorstore_path = ARISConfig.get_vectorstore_path()
                if hasattr(container.gateway_service, 'load_vectorstore'):
                    container.gateway_service.load_vectorstore(vectorstore_path)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Could not re-initialize container: {e}")

# Final check: ensure container exists and documents_processed is set
if st.session_state.documents_processed and container:
    st.header("💬 Ask Questions")
    
    # Display chat history with enhanced citations
    for i, history_item in enumerate(st.session_state.chat_history):
        # Handle both old format (tuple) and new format (dict with citations)
        if isinstance(history_item, tuple):
            question, answer, sources = history_item
            citations = None
        else:
            question = history_item.get('question', '')
            answer = history_item.get('answer', '')
            sources = history_item.get('sources', [])
            citations = history_item.get('citations', None)
        
        with st.chat_message("user"):
            st.write(question)
        
        with st.chat_message("assistant"):
            st.write(answer)
            
            # Show enhanced citations if available
            if citations and len(citations) > 0:
                # Show citation references
                citation_refs = []
                for citation in citations:
                    citation_id = citation.get('id', '?')
                    source_name = citation.get('source', 'Unknown')
                    page = citation.get('page') or 1
                    similarity_percentage = citation.get('similarity_percentage')
                    # Always show page number - page is guaranteed to be >= 1
                    if similarity_percentage is not None:
                        citation_refs.append(f"[{citation_id}] {source_name}, Page {page} ({similarity_percentage:.1f}%)")
                    else:
                        citation_refs.append(f"[{citation_id}] {source_name}, Page {page} (N/A)")
                
                if citation_refs:
                    st.caption("**📎 References:** " + " | ".join(citation_refs))
                
                # Show detailed citations
                with st.expander("📎 Sources & Citations", expanded=False):
                    for citation in citations:
                        citation_id = citation.get('id', '?')
                        source_name = citation.get('source', 'Unknown')
                        page = citation.get('page') or 1
                        snippet = citation.get('snippet', citation.get('full_text', ''))
                        source_location = citation.get('source_location', f"Page {page or 1}")
                        # Handle None values explicitly to avoid TypeError
                        relevance_score = citation.get('relevance_score')
                        if relevance_score is None:
                            relevance_score = 0
                        
                        # Get similarity percentage for display
                        similarity_percentage = citation.get('similarity_percentage')
                        similarity_score = citation.get('similarity_score')
                        
                        # Display citation header with similarity percentage and page number
                        citation_header = f"**[{citation_id}] {source_name}**"
                        citation_header += f" - **Page {page or 1}**"
                        
                        # Show similarity percentage prominently if available
                        if similarity_percentage is not None:
                            # Color-code based on similarity percentage
                            if similarity_percentage >= 80:
                                st.success(f"⭐ **Rank {citation_id} - Similarity: {similarity_percentage:.1f}%** - {source_name} - Page {page or 1}")
                            elif similarity_percentage >= 50:
                                st.info(f"📊 **Rank {citation_id} - Similarity: {similarity_percentage:.1f}%** - {source_name} - Page {page or 1}")
                            else:
                                st.caption(f"📋 **Rank {citation_id} - Similarity: {similarity_percentage:.1f}%** - {source_name} - Page {page or 1}")
                        elif similarity_score is not None:
                            # Fallback to similarity score if percentage not available
                            st.info(f"📊 **Rank {citation_id} - Score: {similarity_score:.4f}** - {source_name} - Page {page or 1}")
                        else:
                            # No similarity data available
                            st.markdown(f"**Rank {citation_id}** - {source_name} - Page {page or 1}")
                        
                        # Show source location with page number
                        if page:
                            st.success(f"📍 **Source Location:** {source_location}")
                        else:
                            st.info(f"📍 **Source Location:** {source_location}")
                        
                        st.markdown(citation_header)
                        
                        # Show snippet
                        if snippet and snippet.strip():
                            import re
                            snippet_clean = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', snippet).strip()
                            if not snippet_clean:
                                snippet_clean = snippet
                            st.text_area(
                                f"Source text from citation [{citation_id}]:",
                                snippet_clean[:500] + "..." if len(snippet_clean) > 500 else snippet_clean,
                                height=100,
                                key=f"history_citation_{i}_{citation_id}",
                                label_visibility="visible"
                            )
                        st.divider()
            elif sources:
                # Fallback to simple display if no citations
                with st.expander("📎 Sources"):
                    for source in sources:
                        st.write(f"- {source}")
    
    # Query Mode Selection
    query_mode = st.radio(
        "Query Mode:",
        ["💬 Text Questions", "🖼️ Image Search"],
        index=0,
        horizontal=True,
        help="Choose to ask questions about text content or search for images/diagrams"
    )

    if query_mode == "💬 Text Questions":
        # Single Query Input (at the top)
        st.subheader("💬 Ask Questions")
        question = st.chat_input("Ask a question about your documents...")
    else:
        # Image Query Interface
        st.subheader("🖼️ Search Images & Diagrams")
        question = st.text_input(
            "Search for images:",
            placeholder="e.g., technical diagrams, charts, tables...",
            help="Search for images, diagrams, and visual content in your documents"
        )
        search_images = st.button("🔍 Search Images", type="primary", disabled=not question)

        # Image Query Processing
        if question and search_images:
            with st.chat_message("user"):
                st.write(f"🖼️ Searching for: **{question}**")

            with st.chat_message("assistant"):
                with st.spinner("Searching images..."):
                    container = st.session_state.get('service_container')
                    if not container:
                        # Initialize service container if it doesn't exist
                        try:
                            st.session_state.service_container = ServiceContainer()
                            container = st.session_state.service_container
                            logger.info("Service container initialized for image query")
                        except Exception as e:
                            st.error(f"Failed to initialize service container: {e}")
                            st.stop()

                    try:
                        # Use same document filtering as text queries
                        images = container.query_images_only(
                            question,
                            k=20  # More images for visual search
                        )

                        if images:
                            st.success(f"Found {len(images)} images matching '{question}'")

                            # Display images in a grid
                            cols = st.columns(3)
                            for i, img in enumerate(images):
                                with cols[i % 3]:
                                    with st.expander(f"Image {img.get('image_number', i+1)}", expanded=False):
                                        st.write(f"**Source:** {img.get('source', 'N/A')}")
                                        st.write(f"**Page:** {img.get('page', 'N/A')}")
                                        if img.get('ocr_text'):
                                            st.text_area(
                                                "OCR Text:",
                                                value=img['ocr_text'][:500] + "..." if len(img['ocr_text']) > 500 else img['ocr_text'],
                                                height=100,
                                                disabled=True,
                                                key=f"ocr_{i}"
                                            )
                                        if img.get('score'):
                                            st.caption(f"Relevance: {img['score']:.3f}")
                        else:
                            st.info("No images found matching your search. Try different keywords or check if your documents contain images.")

                        # Store in citations history for consistency
                        st.session_state.citations_history.append({
                            "question": question,
                            "images": images,
                            "timestamp": time.time(),
                            "mode": "images"
                        })

                    except Exception as e:
                        st.error(f"Image search failed: {str(e)}")
            st.stop()  # Exit after processing image query

    # Only show text query features for text mode
    if query_mode == "💬 Text Questions":
        # Feature Toggles (Compact) - Only show for text queries
        st.markdown("**⚙️ Features:**")
    feature_cols = st.columns(4)
    
    with feature_cols[0]:
        use_agentic_rag = st.checkbox(
            "🤖 Agentic RAG",
            value=st.session_state.get('use_agentic_rag', True),
            help="Break down complex queries into sub-queries"
        )
        st.session_state['use_agentic_rag'] = use_agentic_rag
    
    with feature_cols[1]:
        show_gen_settings = st.checkbox(
            "⚙️ Generation Settings",
            value=st.session_state.get('show_gen_settings', False),
            help="Temperature and Max Tokens"
        )
        st.session_state['show_gen_settings'] = show_gen_settings
    
    with feature_cols[2]:
        show_search_mode = st.checkbox(
            "🔍 Search Mode",
            value=st.session_state.get('show_search_mode', False),
            help="Semantic/Keyword/Hybrid search"
        )
        st.session_state['show_search_mode'] = show_search_mode
    
    with feature_cols[3]:
        enable_multi_mode = st.checkbox(
            "🔬 Multi-Mode Test",
            value=st.session_state.get('enable_multi_mode', False),
            help="Compare different search modes"
        )
        st.session_state['enable_multi_mode'] = enable_multi_mode
    
    # Generation Settings (Collapsible)
    if show_gen_settings:
        with st.expander("⚙️ Generation Settings", expanded=True):
            gen_cols = st.columns(2)
            with gen_cols[0]:
                temperature = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=2.0,
                    value=ARISConfig.DEFAULT_TEMPERATURE,
                    step=0.1,
                    help="Controls randomness (0.0 = deterministic, 2.0 = creative)"
                )
                st.session_state['temperature'] = temperature
            with gen_cols[1]:
                max_tokens = st.slider(
                    "Max Tokens",
                    min_value=100,
                    max_value=4000,
                    value=ARISConfig.DEFAULT_MAX_TOKENS,
                    step=100,
                    help="Maximum response length"
                )
                st.session_state['max_tokens'] = max_tokens
    else:
        temperature = st.session_state.get('temperature', ARISConfig.DEFAULT_TEMPERATURE)
        max_tokens = st.session_state.get('max_tokens', ARISConfig.DEFAULT_MAX_TOKENS)
    
    # Search Mode (Collapsible)
    container = st.session_state.get('service_container')
    if show_search_mode and container and hasattr(container.gateway_service, 'vector_store_type') and \
       container.gateway_service.vector_store_type.lower() == 'opensearch':
        with st.expander("🔍 Search Mode", expanded=True):
            search_mode = st.radio(
                "Select search mode:",
                ["Semantic Only", "Keyword Only", "Hybrid"],
                index=2,  # Default to Hybrid (optimized for cross-language)
                help="Semantic: Vector similarity | Keyword: Text matching | Hybrid: Combined results (recommended)"
            )
            
            semantic_weight = ARISConfig.DEFAULT_SEMANTIC_WEIGHT
            if search_mode == "Hybrid":
                semantic_weight = st.slider(
                    "Semantic Weight",
                    min_value=0.0,
                    max_value=1.0,
                    value=ARISConfig.DEFAULT_SEMANTIC_WEIGHT,
                    step=0.1,
                    help=f"Weight for semantic search. Default is {ARISConfig.DEFAULT_SEMANTIC_WEIGHT} for optimal cross-language performance."
                )
                keyword_weight = 1.0 - semantic_weight
                st.caption(f"Keyword Weight: {keyword_weight:.1f}")
            elif search_mode == "Keyword Only":
                semantic_weight = 0.0
            else:  # Semantic Only
                semantic_weight = 1.0
    else:
        # Default: Hybrid (per user request and backend optimization)
        search_mode = "Hybrid"
        semantic_weight = ARISConfig.DEFAULT_SEMANTIC_WEIGHT
    
    # Only process text queries in text mode
    if query_mode == "💬 Text Questions":
        # Info message if no document is selected for summary queries (less intrusive)
        if question and question.lower().strip():
            is_summary_like = any(kw in question.lower() for kw in ['summary', 'summarize', 'overview', 'what is this document about', 'what does this document contain'])
            if is_summary_like:
                container = st.session_state.get('service_container')
                if not container or not container.gateway_service.active_sources:
                    st.info("💡 **Tip:** Select a document from the sidebar to get a summary of that specific document. Currently searching all documents.")

        if question:
            # Add user question to chat
            st.chat_message("user").write(question)
            
            # Get answer with improved accuracy settings
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    # Map UI search mode to API parameter
                    search_mode_param = search_mode.lower().replace(" only", "").replace(" ", "_")
                    if search_mode_param == "semantic":
                        search_mode_param = "semantic"
                    elif search_mode_param == "keyword":
                        search_mode_param = "keyword"
                    else:
                        search_mode_param = "hybrid"
                    
                    # Check if hybrid search is available and provide feedback
                    container = st.session_state.get('service_container')
                    if search_mode_param in ["hybrid", "keyword"] and \
                       container and hasattr(container.gateway_service, 'vector_store_type') and \
                       container.gateway_service.vector_store_type.lower() != 'opensearch':
                        st.info("ℹ️ Hybrid search is only available for OpenSearch. Using semantic search instead.")
                        search_mode_param = "semantic"
                        semantic_weight = 1.0
                    
                    # Use maximum accuracy settings: more chunks, optimized MMR
                    # k and use_mmr will use config defaults optimized for accuracy
                    container = st.session_state.get('service_container')
                    if not container:
                        # Initialize service container if it doesn't exist
                        try:
                            st.session_state.service_container = ServiceContainer()
                            container = st.session_state.service_container
                            logger.info("Service container initialized for text query")
                        except Exception as e:
                            st.error(f"Failed to initialize service container: {e}")
                            st.stop()
                    result = container.query_with_rag(
                        question,
                        use_hybrid_search=(search_mode_param == "hybrid" or search_mode_param == "keyword"),
                        semantic_weight=semantic_weight,
                        search_mode=search_mode_param,
                        use_agentic_rag=use_agentic_rag,
                        temperature=temperature,  # NEW: Pass UI temperature
                        max_tokens=max_tokens,  # NEW: Pass UI max_tokens
                        response_language=response_language,
                        filter_language=filter_language,
                        auto_translate=auto_translate
                    )
                    answer = result["answer"]
                    sources = result.get("sources", [])
                    citations = result.get("citations", [])
                    num_chunks = result.get("num_chunks_used", 0)
                    context_chunks = result.get("context_chunks", [])
                    sub_queries = result.get("sub_queries", [])
                
                # Display sub-queries if Agentic RAG was used
                if use_agentic_rag and sub_queries and len(sub_queries) > 1:
                    with st.expander("🔍 Sub-Queries Analyzed", expanded=False):
                        st.write("**Original Question:** " + question)
                        st.write("**Sub-Questions:**")
                        for i, sq in enumerate(sub_queries, 1):
                            st.write(f"{i}. {sq}")
                
                # Ensure citations exist - create from sources if missing
                # Also try to extract from context_chunks if available
                if (not citations or len(citations) == 0) and sources:
                    # Try to create citations from context_chunks if available
                    if "context_chunks" in result and len(result["context_chunks"]) > 0:
                        citations = []
                        import re
                        for idx, chunk_item in enumerate(result["context_chunks"], 1):
                            # Handle both string chunks and Document objects with metadata
                            if isinstance(chunk_item, dict) and 'page_content' in chunk_item:
                                # Document-like object with metadata
                                chunk_text = chunk_item.get('page_content', '')
                                chunk_metadata = chunk_item.get('metadata', {})
                                # Prioritize metadata over text markers
                                page = chunk_metadata.get('source_page') or chunk_metadata.get('page') or None
                            elif isinstance(chunk_item, str):
                                # Plain string chunk
                                chunk_text = chunk_item
                                chunk_metadata = {}
                                page = None
                            else:
                                # Fallback: treat as string
                                chunk_text = str(chunk_item)
                                chunk_metadata = {}
                                page = None
                            
                            # If no page from metadata, try to extract from text markers
                            if not page:
                                page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                                if page_match:
                                    page = int(page_match.group(1))
                            
                            # Validate page number - page should be positive
                            if page and page < 1:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"Invalid page number {page} extracted from chunk")
                                page = None
                            
                            # Ensure page is always set (fallback to 1)
                            page = page or 1
                            
                            # Extract source from chunk text metadata markers if available
                            # Look for [Source X: filename] pattern in chunk
                            source_match = re.search(r'\[Source\s+\d+:\s*([^\]]+?)(?:\s*\(Page\s+\d+\))?\]', chunk_text)
                            if source_match:
                                source = source_match.group(1).strip()
                                # Remove any trailing page info if captured
                                source = re.sub(r'\s*\(Page\s+\d+\)', '', source)
                            else:
                                # Fallback: try to extract from sources list, but prefer first source
                                # since we can't reliably match by index
                                source = sources[0] if sources else 'Unknown'
                            
                            # Clean snippet
                            snippet_clean = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', chunk_text).strip()
                            if not snippet_clean:
                                snippet_clean = chunk_text
                            
                            # Determine content type
                            content_type = 'text'
                            if 'image' in chunk_text.lower() or 'ocr' in chunk_text.lower():
                                content_type = 'image'
                            
                            # Build source location
                            source_location = f"Page {page or 1}"
                            
                            citations.append({
                                'id': idx,
                                'source': source,
                                'page': page or 1,
                                'snippet': snippet_clean[:500] + "..." if len(snippet_clean) > 500 else snippet_clean,
                                'full_text': chunk_text,
                                'source_location': source_location,
                                'content_type': content_type
                            })
                    else:
                        # Create basic citations from sources
                        citations = []
                        for idx, source in enumerate(sources, 1):
                            citations.append({
                                'id': idx,
                                'source': source,
                                'page': 1,
                                'snippet': 'Source information available - expand to see details',
                                'full_text': '',
                                'source_location': 'Page 1',  # Always use page number, default to 1
                                'content_type': 'text'
                            })
                
                # Display answer
                st.markdown(answer)
                
                # Always show citations if they exist, regardless of answer content
                if citations and len(citations) > 0:
                    # Show citation markers below answer
                    citation_refs = []
                    for idx, citation in enumerate(citations, 1):
                        citation_id = citation.get('id', idx)
                        source_name = citation.get('source', 'Unknown')
                        page = citation.get('page') or 1
                        # Always show page number - page is guaranteed to be >= 1
                        citation_refs.append(f"[{citation_id}] {source_name}, Page {page}")
                    
                    if citation_refs:
                        st.caption("**📎 References:** " + " | ".join(citation_refs))
                elif sources and len(sources) > 0:
                    # Fallback: show sources even if citations not available
                    st.caption(f"**📎 Sources:** {', '.join(sources)}")
                
                # Show accuracy metrics and token counts
                if num_chunks > 0:
                    context_tokens = result.get("context_tokens", 0)
                    response_tokens = result.get("response_tokens", 0)
                    total_tokens = result.get("total_tokens", 0)
                    
                    st.caption(
                        f"📊 Used {num_chunks} relevant chunks | "
                        f"🔢 Tokens: {context_tokens:,} (context) + {response_tokens:,} (response) = {total_tokens:,} total"
                    )
                
                # Show detailed sources with citations - ALWAYS show if we have sources or context_chunks
                if sources and len(sources) > 0:
                    # Always show citations panel, expanded by default
                    st.markdown("---")
                    st.subheader("📎 Sources & Citations")
                    
                    # Use citations if available, otherwise use context_chunks
                    items_to_display = []
                    if citations and len(citations) > 0:
                        items_to_display = citations
                        st.info(f"**{len(citations)} source(s) were used to generate this answer:**")
                    elif context_chunks and len(context_chunks) > 0:
                        # Create citation-like objects from context_chunks with enhanced metadata
                        # Create citation-like objects from context_chunks
                        items_to_display = []
                        for idx, chunk_item in enumerate(context_chunks, 1):
                            import re
                            # Handle both string chunks and Document objects with metadata
                            if isinstance(chunk_item, dict) and 'page_content' in chunk_item:
                                # Document-like object with metadata
                                chunk_text = chunk_item.get('page_content', '')
                                chunk_metadata = chunk_item.get('metadata', {})
                                # Prioritize metadata over text markers
                                page = chunk_metadata.get('source_page') or chunk_metadata.get('page') or None
                            elif isinstance(chunk_item, str):
                                # Plain string chunk
                                chunk_text = chunk_item
                                chunk_metadata = {}
                                page = None
                            else:
                                # Fallback: treat as string
                                chunk_text = str(chunk_item)
                                chunk_metadata = {}
                                page = None
                            
                            # If no page from metadata, try to extract from text markers
                            if not page:
                                page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                                if page_match:
                                    page = int(page_match.group(1))
                            
                            # Validate page number if document metadata is available
                            # Basic validation - page should be positive
                            if page and page < 1:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"Invalid page number {page} extracted from chunk")
                                page = None
                            
                            # Ensure page is always set (fallback to 1)
                            page = page or 1
                            
                            # Extract source from chunk text metadata markers if available
                            # Look for [Source X: filename] pattern in chunk
                            source_match = re.search(r'\[Source\s+\d+:\s*([^\]]+?)(?:\s*\(Page\s+\d+\))?\]', chunk_text)
                            if source_match:
                                source = source_match.group(1).strip()
                                # Remove any trailing page info if captured
                                source = re.sub(r'\s*\(Page\s+\d+\)', '', source)
                            else:
                                # Fallback: try to extract from sources list, but prefer first source
                                # since we can't reliably match by index
                                source = sources[0] if sources else 'Unknown'
                            
                            # Extract more metadata from chunk text
                            snippet_clean = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', chunk_text).strip()
                            if not snippet_clean:
                                snippet_clean = chunk_text
                            
                            # Try to determine content type
                            content_type = 'text'
                            if 'image' in chunk_text.lower() or 'ocr' in chunk_text.lower():
                                content_type = 'image'
                            
                            items_to_display.append({
                                'id': idx,
                                'source': source,
                                'page': page or 1,
                                'snippet': snippet_clean[:500] + "..." if len(snippet_clean) > 500 else snippet_clean,
                                'full_text': chunk_text,
                                'source_location': f"Page {page or 1}",
                                'content_type': content_type
                            })
                        st.info(f"**{len(items_to_display)} source(s) were used to generate this answer:**")
                    
                    for idx, item in enumerate(items_to_display, 1):
                        citation_id = item.get('id', idx)
                        source_name = item.get('source', 'Unknown')
                        page = item.get('page') or 1 or 1
                        snippet = item.get('snippet', item.get('full_text', ''))
                        source_location = item.get('source_location', f"Page {page or 1}")
                        image_ref = item.get('image_ref')
                        image_info = item.get('image_info')
                        content_type = item.get('content_type', 'text')
                        
                        # Clean snippet - remove page markers for cleaner display
                        import re
                        snippet_clean = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', snippet).strip()
                        if not snippet_clean:
                            snippet_clean = snippet
                        
                        # Display citation with page number and source location
                        with st.container():
                            # Main citation header with source location (certification)
                            citation_header = f"**[{citation_id}] {source_name}**"
                            
                            # Show confidence indicators and relevance score
                            # Handle None values explicitly to avoid TypeError
                            source_confidence = item.get('source_confidence')
                            if source_confidence is None:
                                source_confidence = 0
                            page_confidence = item.get('page_confidence')
                            if page_confidence is None:
                                page_confidence = 0
                            relevance_score = item.get('relevance_score')
                            if relevance_score is None:
                                relevance_score = 0
                            extraction_method = item.get('extraction_method', 'unknown')
                            
                            # Show relevance ranking prominently at the top
                            if relevance_score > 0:
                                st.markdown("---")
                                if relevance_score >= 0.7:
                                    st.success(f"🏆 **Rank #{citation_id} - High Relevance Score: {relevance_score:.1%}** (Most relevant citation)")
                                elif relevance_score >= 0.4:
                                    st.info(f"📊 **Rank #{citation_id} - Medium Relevance Score: {relevance_score:.1%}**")
                                else:
                                    st.caption(f"📋 **Rank #{citation_id} - Low Relevance Score: {relevance_score:.1%}**")
                                st.markdown("---")
                            
                            # Confidence badges
                            confidence_cols = st.columns(3)
                            with confidence_cols[0]:
                                if source_confidence >= 0.7:
                                    st.success(f"✓ High Source Confidence ({source_confidence:.0%})")
                                elif source_confidence >= 0.3:
                                    st.warning(f"⚠ Medium Source Confidence ({source_confidence:.0%})")
                                else:
                                    st.error(f"✗ Low Source Confidence ({source_confidence:.0%})")
                            
                            with confidence_cols[1]:
                                if page_confidence >= 0.6:
                                    st.success(f"✓ High Page Confidence ({page_confidence:.0%})")
                                elif page_confidence >= 0.3:
                                    st.warning(f"⚠ Medium Page Confidence ({page_confidence:.0%})")
                                elif page_confidence > 0:
                                    st.error(f"✗ Low Page Confidence ({page_confidence:.0%})")
                                else:
                                    st.info("No page number")
                            
                            with confidence_cols[2]:
                                similarity_percentage = item.get('similarity_percentage')
                                similarity_score = item.get('similarity_score')
                                if similarity_percentage is not None:
                                    # Color-code based on similarity percentage
                                    if similarity_percentage >= 80:
                                        st.success(f"⭐ Similarity: {similarity_percentage:.1f}%")
                                    elif similarity_percentage >= 50:
                                        st.info(f"📊 Similarity: {similarity_percentage:.1f}%")
                                    else:
                                        st.caption(f"📋 Similarity: {similarity_percentage:.1f}%")
                                elif similarity_score is not None:
                                    st.info(f"🔍 Score: {similarity_score:.3f}")
                                else:
                                    st.caption("🔍 Similarity: N/A")
                            
                            # Show similarity percentage prominently at the top
                            similarity_percentage = item.get('similarity_percentage')
                            similarity_score = item.get('similarity_score')
                            if similarity_percentage is not None:
                                st.markdown("---")
                                if similarity_percentage >= 80:
                                    st.success(f"⭐ **Rank #{citation_id} - Similarity: {similarity_percentage:.1f}%** - {source_name} - Page {page or 1} (Most relevant)")
                                elif similarity_percentage >= 50:
                                    st.info(f"📊 **Rank #{citation_id} - Similarity: {similarity_percentage:.1f}%** - {source_name} - Page {page or 1}")
                                else:
                                    st.caption(f"📋 **Rank #{citation_id} - Similarity: {similarity_percentage:.1f}%** - {source_name} - Page {page or 1}")
                                st.markdown("---")
                            elif similarity_score is not None:
                                st.markdown("---")
                                st.info(f"📊 **Rank #{citation_id} - Score: {similarity_score:.4f}** - {source_name} - Page {page or 1}")
                                st.markdown("---")
                            # Show relevance ranking prominently (fallback if similarity not available)
                            elif relevance_score > 0:
                                st.markdown("---")
                                if relevance_score >= 0.7:
                                    st.success(f"🏆 **Rank #{citation_id} - High Relevance Score: {relevance_score:.1%}** (Most relevant citation)")
                                elif relevance_score >= 0.4:
                                    st.info(f"📊 **Rank #{citation_id} - Medium Relevance Score: {relevance_score:.1%}**")
                                else:
                                    st.caption(f"📋 **Rank #{citation_id} - Low Relevance Score: {relevance_score:.1%}**")
                                st.markdown("---")
                            
                            # Show source location prominently (certification field)
                            if source_location:
                                if image_ref:
                                    st.success(f"📍 **Source Location:** {source_location} | 📷 **Image Reference:** {image_info}")
                                elif page:
                                    st.success(f"📍 **Source Location:** {source_location}")
                                else:
                                    st.info(f"📍 **Source Location:** {source_location}")
                            
                            # Display citation header
                            if page:
                                citation_header += f" - **Page {page}**"
                                if image_ref:
                                    citation_header += f" | 📷 **Image {image_ref.get('image_index', '?')}**"
                                st.markdown(f"### {citation_header}")
                            else:
                                citation_header += " - Page number not available"
                                st.warning(citation_header)
                            
                            # Show extraction method and section if available
                            metadata_row = []
                            if extraction_method and extraction_method != 'unknown':
                                metadata_row.append(f"Extraction: {extraction_method}")
                            if item.get('section'):
                                metadata_row.append(f"Section: {item.get('section')}")
                            if metadata_row:
                                st.caption(" | ".join(metadata_row))
                            
                            # Show content type badge
                            if content_type == 'image':
                                st.markdown("**📷 Image Content**")
                            else:
                                st.markdown("**📄 Text Content**")
                            
                            # Show snippet with more context (up to 500 chars)
                            if snippet_clean and snippet_clean.strip():
                                display_snippet = snippet_clean[:500] + "..." if len(snippet_clean) > 500 else snippet_clean
                                label = f"📄 Source text from citation [{citation_id}]:" if content_type == 'text' else f"📷 Image content/OCR text from citation [{citation_id}]:"
                                st.text_area(
                                    label,
                                    display_snippet,
                                    height=150,
                                    key=f"citation_{citation_id}_{len(st.session_state.chat_history)}_{idx}",
                                    label_visibility="visible"
                                )
                            else:
                                st.caption("No snippet available")
                            
                            # Show image reference details if available
                            if image_ref:
                                image_details = []
                                if image_ref.get('bbox'):
                                    bbox = image_ref['bbox']
                                    image_details.append(f"Position: ({bbox[0]:.1f}, {bbox[1]:.1f}) to ({bbox[2]:.1f}, {bbox[3]:.1f})")
                                if image_ref.get('xref'):
                                    image_details.append(f"XRef: {image_ref['xref']}")
                                if image_details:
                                    st.caption("🖼️ " + " | ".join(image_details))
                            
                            # Show additional metadata if available
                            metadata_info = []
                            if item.get('chunk_index') is not None:
                                metadata_info.append(f"Chunk: {item.get('chunk_index')}")
                            if item.get('start_char') is not None:
                                metadata_info.append(f"Text Position: {item.get('start_char')}-{item.get('end_char')}")
                            if metadata_info:
                                st.caption(" | ".join(metadata_info))
                            
                            if idx < len(items_to_display):
                                st.divider()
                elif sources:
                    # Fallback: Show sources with extracted page numbers from context chunks
                    st.markdown("---")
                    st.subheader("📎 Sources & Citations")
                    st.info(f"**{len(sources)} source(s) were used to generate this answer:**")
                    
                    # Try to extract page numbers from context_chunks
                    context_chunks = result.get("context_chunks", [])
                    
                    for idx, source in enumerate(sources, 1):
                        with st.container():
                            # Try to find matching chunk for this source
                            chunk_text = ""
                            page = None
                            
                            if context_chunks and idx <= len(context_chunks):
                                chunk_text = context_chunks[idx - 1]
                                # Extract page number from chunk text
                                import re
                                page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                                if page_match:
                                    page = int(page_match.group(1))
                            
                            # Display source with page if found
                            source_header = f"**[{idx}] {source}**"
                            if page:
                                source_header += f" - **Page {page}**"
                                st.success(source_header)
                            else:
                                source_header += " - Page number not available"
                                st.warning(source_header)
                            
                            # Show chunk text if available
                            if chunk_text and chunk_text.strip():
                                # Clean page markers for display
                                clean_chunk = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', chunk_text).strip()
                                if not clean_chunk:
                                    clean_chunk = chunk_text
                                
                                st.text_area(
                                    f"📄 Source text from [{idx}]:",
                                    clean_chunk[:500] + "..." if len(clean_chunk) > 500 else clean_chunk,
                                    height=120,
                                    key=f"source_{idx}_{len(st.session_state.chat_history)}",
                                    label_visibility="visible"
                                )
                            else:
                                st.caption("Source text not available")
                            
                            if idx < len(sources):
                                st.divider()
                else:
                    # Show message if no sources found
                    st.warning("⚠️ No sources found for this answer.")
                
                # =====================================================
                # R&D DETAILED METRICS - Integrated with Main Query
                # =====================================================
                st.markdown("---")
                with st.expander("📊 **R&D Detailed Metrics** (click to expand)", expanded=False):
                    import pandas as pd
                    
                    # Current Query Parameters
                    st.subheader("⚙️ Query Parameters Used")
                    param_cols = st.columns(5)
                    param_cols[0].metric("Search Mode", search_mode_param.upper())
                    param_cols[1].metric("Semantic Weight", f"{semantic_weight:.2f}")
                    param_cols[2].metric("Temperature", f"{temperature:.1f}")
                    param_cols[3].metric("Max Tokens", max_tokens)
                    param_cols[4].metric("Chunks (k)", num_chunks)
                    
                    st.divider()
                    
                    # Detailed citation metrics
                    if citations and len(citations) > 0:
                        st.subheader("📈 Citation Score Analysis")
                        
                        # Calculate detailed stats
                        similarities = [c.get('similarity_percentage', 0) for c in citations]
                        
                        if similarities and any(s > 0 for s in similarities):
                            # Stats row
                            stats_cols = st.columns(5)
                            stats_cols[0].metric("Max Similarity", f"{max(similarities):.1f}%")
                            stats_cols[1].metric("Min Similarity", f"{min(similarities):.1f}%")
                            avg_sim = sum(similarities)/len(similarities)
                            stats_cols[2].metric("Average", f"{avg_sim:.1f}%")
                            
                            # Standard deviation
                            variance = sum((x - avg_sim) ** 2 for x in similarities) / len(similarities)
                            std_dev = variance ** 0.5
                            stats_cols[3].metric("Std Dev", f"{std_dev:.1f}")
                            
                            # Score spread
                            spread = max(similarities) - min(similarities)
                            stats_cols[4].metric("Spread", f"{spread:.1f}%")
                            
                            st.divider()
                            
                            # Individual scores table
                            st.markdown("**Individual Citation Scores:**")
                            citation_rows = []
                            for i, c in enumerate(citations):
                                citation_rows.append({
                                    'Rank': i + 1,
                                    'Similarity %': f"{c.get('similarity_percentage', 0):.1f}%",
                                    'Score': f"{c.get('similarity_score', 0):.4f}" if c.get('similarity_score') else 'N/A',
                                    'Source': c.get('source', 'Unknown')[:30],
                                    'Page': c.get('page', 1),
                                    'Image': c.get('image_number', '-') or '-',
                                    'Type': c.get('content_type', 'text')
                                })
                            
                            citation_df = pd.DataFrame(citation_rows)
                            st.dataframe(citation_df, use_container_width=True, hide_index=True)
                            
                            # Visual similarity distribution
                            st.markdown("**Similarity Score Distribution:**")
                            for i, sim in enumerate(similarities):
                                source = citations[i].get('source', 'Unknown')[:25]
                                bar_width = int(sim / 2)  # Scale to 50 chars max
                                bar = '█' * bar_width + '░' * (50 - bar_width)
                                color = "🟢" if sim >= 80 else ("🟡" if sim >= 50 else "🔴")
                                st.code(f"{color} #{i+1} [{sim:5.1f}%] {bar} {source}")
                        else:
                            st.info("Similarity scores not available for detailed analysis")
                        
                        st.divider()
                        
                        # Token usage
                        st.subheader("🔢 Token Usage")
                        token_cols = st.columns(4)
                        context_tokens = result.get("context_tokens", 0)
                        response_tokens = result.get("response_tokens", 0)
                        total_tokens = result.get("total_tokens", context_tokens + response_tokens)
                        
                        token_cols[0].metric("Context Tokens", f"{context_tokens:,}")
                        token_cols[1].metric("Response Tokens", f"{response_tokens:,}")
                        token_cols[2].metric("Total Tokens", f"{total_tokens:,}")
                        token_cols[3].metric("Answer Length", f"{len(answer):,} chars")
                        
                        st.divider()
                        
                        # Export button for this query
                        st.subheader("📥 Export Query Results")
                        import json
                        export_data = {
                            'query': question,
                            'parameters': {
                                'search_mode': search_mode_param,
                                'semantic_weight': semantic_weight,
                                'temperature': temperature,
                                'max_tokens': max_tokens,
                                'auto_translate': auto_translate
                            },
                            'results': {
                                'num_citations': len(citations),
                                'similarities': similarities,
                                'max_similarity': max(similarities) if similarities else 0,
                                'min_similarity': min(similarities) if similarities else 0,
                                'avg_similarity': sum(similarities)/len(similarities) if similarities else 0,
                                'context_tokens': context_tokens,
                                'response_tokens': response_tokens,
                                'answer_length': len(answer)
                            },
                            'citations': [
                                {
                                    'source': c.get('source'),
                                    'page': c.get('page'),
                                    'similarity': c.get('similarity_percentage', 0)
                                }
                                for c in citations
                            ]
                        }
                        
                        export_json = json.dumps(export_data, indent=2)
                        st.download_button(
                            label="📥 Download Query Metrics (JSON)",
                            data=export_json,
                            file_name=f"query_metrics_{len(st.session_state.chat_history)}.json",
                            mime="application/json",
                            key=f"export_btn_{len(st.session_state.chat_history)}"
                        )
                    else:
                        st.info("No citation data available for detailed metrics")
            
            # Store citations in session state for persistent display
            if citations and len(citations) > 0:
                st.session_state.citations_history.append({
                    'question': question,
                    'answer': answer,
                    'citations': citations,
                    'sources': sources,
                    'num_chunks': num_chunks,
                    'context_chunks': context_chunks
                })
            elif context_chunks and len(context_chunks) > 0:
                # Create citations from context_chunks if not available
                import re
                created_citations = []
                for idx, chunk_item in enumerate(context_chunks, 1):
                    # Handle both string chunks and Document objects with metadata
                    if isinstance(chunk_item, dict) and 'page_content' in chunk_item:
                        # Document-like object with metadata
                        chunk_text = chunk_item.get('page_content', '')
                        chunk_metadata = chunk_item.get('metadata', {})
                        # Prioritize metadata over text markers
                        page = chunk_metadata.get('source_page') or chunk_metadata.get('page') or None
                    elif isinstance(chunk_item, str):
                        # Plain string chunk (most common case)
                        chunk_text = chunk_item
                        chunk_metadata = {}
                        page = None
                    else:
                        # Fallback: treat as string
                        chunk_text = str(chunk_item)
                        chunk_metadata = {}
                        page = None
                    
                    # If no page from metadata, try to extract from text markers
                    if not page:
                        page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                        if page_match:
                            page = int(page_match.group(1))
                    
                    # Validate page number - page should be positive
                    if page and page < 1:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Invalid page number {page} extracted from chunk")
                        page = None
                    
                    # Ensure page is always set (fallback to 1)
                    page = page or 1
                    
                    # Extract source from chunk text metadata markers if available
                    # Look for [Source X: filename] pattern in chunk
                    source_match = re.search(r'\[Source\s+\d+:\s*([^\]]+?)(?:\s*\(Page\s+\d+\))?\]', chunk_text)
                    if source_match:
                        source = source_match.group(1).strip()
                        # Remove any trailing page info if captured
                        source = re.sub(r'\s*\(Page\s+\d+\)', '', source)
                    else:
                        # Fallback: try to extract from sources list, but prefer first source
                        # since we can't reliably match by index
                        source = sources[0] if sources else 'Unknown'
                    
                    # Clean snippet
                    snippet_clean = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', chunk_text).strip()
                    if not snippet_clean:
                        snippet_clean = chunk_text
                    
                    # Determine content type
                    content_type = 'text'
                    if 'image' in chunk_text.lower() or 'ocr' in chunk_text.lower():
                        content_type = 'image'
                    
                    # Build source location
                    source_location = f"Page {page or 1}"
                    
                    created_citations.append({
                        'id': idx,
                        'source': source,
                        'page': page or 1,
                        'snippet': snippet_clean[:500] + "..." if len(snippet_clean) > 500 else snippet_clean,
                        'full_text': chunk_text,
                        'source_location': source_location,
                        'content_type': content_type
                    })
                st.session_state.citations_history.append({
                    'question': question,
                    'answer': answer,
                    'citations': created_citations,
                    'sources': sources,
                    'num_chunks': num_chunks,
                    'context_chunks': context_chunks
                })
            
            # Add to chat history with citations
            # Store as dict to preserve citations
            history_entry = {
                'question': question,
                'answer': answer,
                'sources': sources,
                'citations': citations if citations and len(citations) > 0 else None
            }
            st.session_state.chat_history.append(history_entry)
            st.rerun()
    
    # ============================================
    # MULTI-MODE COMPARISON (Only if enabled)
    # ============================================
    if enable_multi_mode:
        st.divider()
        st.header("🔬 Multi-Mode Comparison")
        
        # Get last query from chat history (uses main query)
        last_query = None
        if st.session_state.chat_history:
            last_entry = st.session_state.chat_history[-1]
            if isinstance(last_entry, dict):
                last_query = last_entry.get('question', '')
            elif isinstance(last_entry, tuple) and len(last_entry) >= 1:
                last_query = last_entry[0]
        
        if not last_query:
            st.info("💡 Ask a question in the main chat above, then come back here to compare modes.")
        else:
            st.info(f"📝 **Using your last query:** \"{last_query[:80]}{'...' if len(last_query) > 80 else ''}\"")
            
            # Compact configuration
            st.markdown("**⚙️ Test Parameters:**")
            cfg_cols = st.columns(4)
            
            with cfg_cols[0]:
                test_k = st.slider("Chunks (k):", 3, 20, 10, key="mm_k")
            with cfg_cols[1]:
                test_semantic_weight = st.slider("Semantic Wt:", 0.0, 1.0, 0.7, 0.05, key="mm_sem_wt")
            with cfg_cols[2]:
                test_temperature = st.slider("Temp:", 0.0, 1.0, 0.2, 0.1, key="mm_temp")
            with cfg_cols[3]:
                native_language = st.selectbox("Native Lang:", ["Spanish", "French", "German", "Italian", "Portuguese"], key="mm_lang")
            
            # Test modes to run
            st.markdown("**🔧 Modes to Compare:**")
            mode_cols = st.columns(4)
            with mode_cols[0]:
                test_hybrid = st.checkbox("Hybrid", value=True, key="mm_hybrid")
            with mode_cols[1]:
                test_semantic = st.checkbox("Semantic", value=True, key="mm_semantic")
            with mode_cols[2]:
                test_keyword = st.checkbox("Keyword", value=True, key="mm_keyword")
            with mode_cols[3]:
                test_with_translate = st.checkbox("+ Auto-Translate", value=True, key="mm_translate")
            
            # Run comparison button
            if st.button("🔬 Run Multi-Mode Comparison", key="run_multi_mode_test", type="primary"):
                if not last_query or not last_query.strip():
                    st.error("Please ask a question in the main chat first.")
                else:
                    container = st.session_state.get('service_container')
                    if not container:
                        st.error("Service container not initialized. Please upload a document first.")
                    else:
                        results = {}
                        import time as time_module
                        import pandas as pd
                        
                        # Store test parameters for display
                        test_params = {
                            'k': test_k,
                            'semantic_weight': test_semantic_weight,
                            'temperature': test_temperature
                        }
                        
                        query = last_query.strip()
                        
                        with st.spinner("Running multi-mode comparison..."):
                            # Define modes to test
                            modes_to_test = []
                            if test_hybrid:
                                modes_to_test.append(('hybrid', 'Hybrid', test_semantic_weight, False))
                            if test_semantic:
                                modes_to_test.append(('semantic', 'Semantic', 1.0, False))
                            if test_keyword:
                                modes_to_test.append(('keyword', 'Keyword', 0.0, False))
                            if test_with_translate and test_hybrid:
                                modes_to_test.append(('hybrid', 'Hybrid + Translate', test_semantic_weight, True))
                            
                            for mode, mode_name, sem_wt, auto_trans in modes_to_test:
                                st.info(f"🔄 Running: **{mode_name}**...")
                                try:
                                    start_time = time_module.time()
                                    result = container.query_with_rag(
                                        query,
                                        k=test_k,
                                        use_hybrid_search=(mode == "hybrid" or mode == "keyword"),
                                        semantic_weight=sem_wt,
                                        search_mode=mode,
                                        use_agentic_rag=False,
                                        temperature=test_temperature,
                                        auto_translate=auto_trans
                                    )
                                    elapsed = time_module.time() - start_time
                                    
                                    results[mode_name] = {
                                        'answer': result.get('answer', ''),
                                        'citations': result.get('citations', []),
                                        'sources': result.get('sources', []),
                                        'num_chunks': result.get('num_chunks_used', 0),
                                        'context_tokens': result.get('context_tokens', 0),
                                        'response_tokens': result.get('response_tokens', 0),
                                        'response_time': elapsed,
                                        'query': query,
                                        'mode': mode,
                                        'semantic_weight': sem_wt,
                                        'auto_translate': auto_trans
                                    }
                                except Exception as e:
                                    results[mode_name] = {'error': str(e)}
                        
                        # Display comparison results
                        st.success(f"✅ Compared {len(results)} modes for query: \"{query[:50]}...\"")
                        
                        # Show test parameters
                        st.caption(f"Parameters: k={test_k}, semantic_weight={test_semantic_weight}, temp={test_temperature}")
                        
                        st.divider()
                        
                        # Metrics comparison table
                        st.subheader("📊 Mode Comparison")
                    
                    metrics_data = []
                    for mode_name, data in results.items():
                        if 'error' not in data:
                            citations = data.get('citations', [])
                            similarities = [c.get('similarity_percentage', 0) for c in citations]
                            
                            row = {
                                'Mode': mode_name,
                                'Citations': len(citations),
                                'Time': f"{data.get('response_time', 0):.2f}s",
                                'Max%': f"{max(similarities):.1f}" if similarities else 'N/A',
                                'Avg%': f"{sum(similarities)/len(similarities):.1f}" if similarities else 'N/A',
                                'Min%': f"{min(similarities):.1f}" if similarities else 'N/A',
                            }
                            metrics_data.append(row)
                        else:
                            metrics_data.append({'Mode': mode_name, 'Error': data.get('error', 'Unknown error')})
                    
                    if metrics_data:
                        df = pd.DataFrame(metrics_data)
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    # Find best mode
                    best_mode = None
                    best_avg = 0
                    for mode_name, data in results.items():
                        if 'error' not in data:
                            citations = data.get('citations', [])
                            if citations:
                                similarities = [c.get('similarity_percentage', 0) for c in citations]
                                avg = sum(similarities) / len(similarities) if similarities else 0
                                if avg > best_avg:
                                    best_avg = avg
                                    best_mode = mode_name
                    
                    if best_mode:
                        st.success(f"🏆 **Best Mode: {best_mode}** with {best_avg:.1f}% average similarity")
                        
                        # Detailed analysis and recommendations
                        st.markdown("---")
                        st.subheader("💡 Analysis & Recommendations")
                        
                        # Compare best mode to others
                        best_data = results[best_mode]
                        best_citations = best_data.get('citations', [])
                        best_time = best_data.get('response_time', 0)
                        best_sim = best_avg
                        
                        analysis_points = []
                        
                        # Check if best mode is significantly better
                        for mode_name, data in results.items():
                            if mode_name != best_mode and 'error' not in data:
                                other_sim = sum(c.get('similarity_percentage', 0) for c in data.get('citations', [])) / len(data.get('citations', [])) if data.get('citations') else 0
                                other_time = data.get('response_time', 0)
                                
                                if best_sim - other_sim > 10:
                                    analysis_points.append(f"✅ **{best_mode}** is **{best_sim - other_sim:.1f}% more accurate** than {mode_name} ({other_sim:.1f}%)")
                                
                                if best_time < other_time * 0.7:  # At least 30% faster
                                    speedup = ((other_time - best_time) / other_time) * 100
                                    analysis_points.append(f"⚡ **{best_mode}** is **{speedup:.0f}% faster** than {mode_name} ({best_time:.1f}s vs {other_time:.1f}s)")
                        
                        # Quality vs quantity analysis
                        if best_mode == "Semantic":
                            if len(best_citations) < 5:
                                analysis_points.append(f"📊 **Semantic mode** found {len(best_citations)} highly relevant citations (quality over quantity)")
                            analysis_points.append("🎯 **Recommendation:** Use **Semantic mode** as default for conceptual/descriptive queries")
                        
                        elif best_mode == "Hybrid":
                            analysis_points.append("🎯 **Recommendation:** Use **Hybrid mode** when you need both semantic understanding and keyword matching")
                            if best_data.get('semantic_weight', 0.7) >= 0.7:
                                analysis_points.append(f"⚖️ Current semantic weight ({best_data.get('semantic_weight', 0.7):.2f}) favors semantic search")
                        
                        elif best_mode == "Keyword":
                            analysis_points.append("🎯 **Recommendation:** Use **Keyword mode** for exact term/phrase matching queries")
                        
                        # Performance summary
                        if best_sim >= 90:
                            analysis_points.append("⭐ **Excellent match quality** - Results are highly relevant to your query")
                        elif best_sim >= 75:
                            analysis_points.append("✅ **Good match quality** - Results are relevant with minor gaps")
                        elif best_sim >= 60:
                            analysis_points.append("⚠️ **Moderate match quality** - Consider refining your query for better results")
                        
                        for point in analysis_points:
                            st.markdown(point)
                        
                        st.divider()
                        
                        # Detailed view per mode
                        st.subheader("📈 Detailed Results by Mode")
                        
                        for mode_name, data in results.items():
                            if 'error' not in data:
                                with st.expander(f"**{mode_name}** - Details", expanded=False):
                                    citations = data.get('citations', [])
                                    
                                    if citations:
                                        # Visual similarity bars
                                        st.markdown("**Similarity Scores:**")
                                        for i, c in enumerate(citations[:5]):  # Top 5
                                            sim = c.get('similarity_percentage', 0)
                                            source = c.get('source', 'Unknown')[:25]
                                            bar_width = int(sim / 2)
                                            bar = '█' * bar_width + '░' * (50 - bar_width)
                                            color = "🟢" if sim >= 80 else ("🟡" if sim >= 50 else "🔴")
                                            st.code(f"{color} #{i+1} [{sim:5.1f}%] {bar} {source}")
                                        
                                        if len(citations) > 5:
                                            st.caption(f"... and {len(citations) - 5} more citations")
                                    
                                    # Answer preview
                                    answer = data.get('answer', '')
                                    st.markdown("**Answer Preview:**")
                                    st.text_area("", value=answer[:500] + "..." if len(answer) > 500 else answer, 
                                               height=100, key=f"ans_{mode_name}", disabled=True)
                        
                        # Export
                        st.divider()
                        import json
                        export_data = {
                            'query': query,
                            'test_params': test_params,
                            'results': {
                                k: {
                                    'citations': len(v.get('citations', [])),
                                    'response_time': v.get('response_time', 0),
                                    'avg_similarity': sum(c.get('similarity_percentage', 0) for c in v.get('citations', [])) / len(v.get('citations', [])) if v.get('citations') else 0
                                } for k, v in results.items() if 'error' not in v
                            }
                        }
                        st.download_button(
                            "📥 Export Results (JSON)",
                            data=json.dumps(export_data, indent=2),
                            file_name="mode_comparison.json",
                            mime="application/json"
                        )

    # End of text query mode condition
    else:
        # If documents are stored but not loaded, guide user
        if 'document_registry' in st.session_state:
            existing_docs = st.session_state.document_registry.list_documents()
            if existing_docs and not st.session_state.documents_processed:
                # Try to auto-enable for OpenSearch
                vector_store_type = ARISConfig.VECTOR_STORE_TYPE.lower()
                if vector_store_type == 'opensearch':
                    # Auto-initialize for OpenSearch
                    try:
                        if 'service_container' not in st.session_state:
                            st.session_state.service_container = ServiceContainer()
                        st.session_state.documents_processed = True
                        st.session_state.vectorstore_loaded = True
                        st.rerun()  # Refresh to show query interface
                    except Exception as e:
                        st.warning(f"Could not connect to retrieval service: {e}")
                else:
                    st.warning(
                        f"📚 You have {len(existing_docs)} stored document(s). "
                        f"Go to the sidebar → Document Library → pick documents → click **Load Selected Documents** to start Q&A."
                    )
            else:
                st.info("👆 Please upload and process documents using the sidebar to start asking questions.")
        else:
            st.info("👆 Please upload and process documents using the sidebar to start asking questions.")
    
    # Instructions
    with st.expander("📖 How to use"):
        st.markdown("""
        ### Steps:
        1. **Load Stored Documents (if any):** Sidebar → Document Library → Load All Stored Documents
        2. **Or Upload New Documents:** Choose API/Parser, upload files
        3. **Process:** Click "Process Documents" (only for new uploads)
        4. **Ask Questions:** Once documents are loaded, type your questions in the chat input
        
        ### Supported Formats:
        - PDF files (.pdf) - Uses PyMuPDF, Docling, or Textract
        - Text files (.txt)
        - Word documents (.docx, .doc)
        
        ### Parser Options:
        - **PyMuPDF**: Fast parser for text-based PDFs (recommended for speed)
        - **Docling**: Extracts the most content, processes all pages automatically. Takes 5-10 minutes but extracts more text than PyMuPDF
        - **Textract**: AWS OCR for scanned/image PDFs (requires AWS credentials)
        
        ### Features:
        - Token-aware chunking (512 tokens per chunk)
        - Real-time processing with progress tracking
        - Source attribution
        - Long-term storage: documents persist across restarts
        """)
