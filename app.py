"""
Streamlit RAG Application with Advanced Parsers and Real-time Processing
"""
import streamlit as st
import os
import io
import json
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from parsers.parser_factory import ParserFactory
from metrics.metrics_collector import MetricsCollector
from utils.chunking_strategies import get_all_strategies, get_chunking_params, validate_custom_params

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="ARIS R&D - RAG Document Q&A",
    page_icon="📚",
    layout="wide"
)

# Initialize session state
if 'rag_system' not in st.session_state:
    st.session_state.rag_system = None
if 'documents_processed' not in st.session_state:
    st.session_state.documents_processed = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'processing_results' not in st.session_state:
    st.session_state.processing_results = []
if 'document_processor' not in st.session_state:
    st.session_state.document_processor = None
if 'metrics_collector' not in st.session_state:
    st.session_state.metrics_collector = MetricsCollector()

def process_uploaded_files(uploaded_files, use_cerebras, parser_preference, 
                          embedding_model, openai_model, cerebras_model,
                          vector_store_type, opensearch_domain, opensearch_index,
                          chunk_size, chunk_overlap):
    """Process uploaded files with real-time progress tracking"""
    if not uploaded_files:
        return False
    
    # Initialize or update RAG system
    # Recreate if API, models, embedding model, vector store, or chunking changed
    needs_reinit = (
        st.session_state.rag_system is None or
        (hasattr(st.session_state.rag_system, 'use_cerebras') and st.session_state.rag_system.use_cerebras != use_cerebras) or
        (hasattr(st.session_state.rag_system, 'embedding_model') and st.session_state.rag_system.embedding_model != embedding_model) or
        (hasattr(st.session_state.rag_system, 'openai_model') and st.session_state.rag_system.openai_model != openai_model) or
        (hasattr(st.session_state.rag_system, 'cerebras_model') and st.session_state.rag_system.cerebras_model != cerebras_model) or
        (hasattr(st.session_state.rag_system, 'vector_store_type') and st.session_state.rag_system.vector_store_type != vector_store_type.lower()) or
        (hasattr(st.session_state.rag_system, 'opensearch_domain') and st.session_state.rag_system.opensearch_domain != opensearch_domain) or
        (hasattr(st.session_state.rag_system, 'chunk_size') and st.session_state.rag_system.chunk_size != chunk_size) or
        (hasattr(st.session_state.rag_system, 'chunk_overlap') and st.session_state.rag_system.chunk_overlap != chunk_overlap)
    )
    
    if needs_reinit:
        # Warn if switching vector stores and data exists
        if (st.session_state.rag_system is not None and 
            hasattr(st.session_state.rag_system, 'vector_store_type') and
            st.session_state.rag_system.vector_store_type != vector_store_type.lower() and
            st.session_state.rag_system.vectorstore is not None):
            st.warning(
                f"⚠️ Switching vector store from {st.session_state.rag_system.vector_store_type.upper()} to {vector_store_type.upper()}. "
                f"Data in the previous store will not be accessible. You may need to reprocess documents."
            )
        
        st.session_state.rag_system = RAGSystem(
            use_cerebras=use_cerebras,
            metrics_collector=st.session_state.metrics_collector,
            embedding_model=embedding_model,
            openai_model=openai_model,
            cerebras_model=cerebras_model,
            vector_store_type=vector_store_type,
            opensearch_domain=opensearch_domain,
            opensearch_index=opensearch_index,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    # Initialize or update document processor
    if (st.session_state.document_processor is None or 
        not hasattr(st.session_state.document_processor, 'rag_system') or
        st.session_state.document_processor.rag_system != st.session_state.rag_system):
        st.session_state.document_processor = DocumentProcessor(st.session_state.rag_system)
    
    # Prepare files for processing
    files_to_process = []
    for uploaded_file in uploaded_files:
        file_content = uploaded_file.read()
        files_to_process.append({
            'path': uploaded_file.name,
            'content': file_content,
            'name': uploaded_file.name
        })
    
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
                
                # Process document
                result = st.session_state.document_processor.process_document(
                    file_path=file_info['path'],
                    file_content=file_info['content'],
                    file_name=file_name,
                    parser_preference=parser_preference,
                    progress_callback=progress_callback
                )
                
                results.append(result)
                
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
    successful_results = [r for r in results if r.status == 'success']
    
    if successful_results:
        st.session_state.documents_processed = True
        total_chunks = sum(r.chunks_created for r in successful_results)
        total_tokens = sum(r.tokens_extracted for r in successful_results)
        st.success(
            f"✅ Processed {len(successful_results)} document(s) into {total_chunks} chunks "
            f"({total_tokens:,} tokens)!"
        )
        return True
    else:
        st.error("No documents were successfully processed.")
        return False

# Main UI
st.title("📚 ARIS R&D - RAG Document Q&A System")
st.markdown("Upload documents and ask questions about them using AI with advanced parsers!")

# Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    # API selection
    api_choice = st.radio(
        "Choose API:",
        ["OpenAI", "Cerebras"],
        help="Select which API to use for generating answers"
    )
    use_cerebras = api_choice == "Cerebras"
    
    # Model selection based on API choice
    st.divider()
    st.header("🤖 Model Settings")
    
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
        openai_model = st.selectbox(
            "OpenAI Model:",
            list(openai_models.keys()),
            index=0,
            help="Select OpenAI model for generating answers"
        )
        # Show description
        with st.expander("ℹ️ Model Description", expanded=False):
            st.write(f"**{openai_model}**")
            st.write(openai_models[openai_model])
        cerebras_model = "llama3.1-8b"  # Default, not used
    else:
        cerebras_model = st.selectbox(
            "Cerebras Model:",
            list(cerebras_models.keys()),
            index=0,
            help="Select Cerebras model for generating answers"
        )
        # Show description
        with st.expander("ℹ️ Model Description", expanded=False):
            st.write(f"**{cerebras_model}**")
            st.write(cerebras_models[cerebras_model])
        openai_model = "gpt-3.5-turbo"  # Default, not used
    
    # Embedding model selection
    embedding_model = st.selectbox(
        "Embedding Model:",
        list(embedding_models.keys()),
        index=0,
        help="Select embedding model for document vectors"
    )
    # Show embedding model description
    with st.expander("ℹ️ Embedding Model Description", expanded=False):
        st.write(f"**{embedding_model}**")
        st.write(embedding_models[embedding_model])
    
    # Parser selection
    st.divider()
    st.header("🔧 Parser Settings")
    parser_choice = st.selectbox(
        "Choose Parser:",
        ["Docling", "PyMuPDF", "Textract"],
        index=0,  # Default to Docling
        help="Docling extracts the most content (processes all pages) but takes 5-10 minutes (recommended). "
             "PyMuPDF is fast for text-based PDFs. "
             "Textract requires AWS credentials and is best for scanned PDFs."
    )
    parser_preference = parser_choice.lower()
    
    # Chunking Strategy selection
    st.divider()
    st.header("✂️ Chunking Strategy")
    
    chunking_strategies = get_all_strategies()
    strategy_options = ["Precise", "Balanced", "Comprehensive", "Custom"]
    
    chunking_strategy = st.selectbox(
        "Choose Chunking Strategy:",
        strategy_options,
        index=1,  # Default to "Balanced"
        help="Select how documents should be split into chunks. "
             "Precise: Small chunks for exact matches. "
             "Balanced: Medium chunks (recommended). "
             "Comprehensive: Large chunks with more context. "
             "Custom: Set your own chunk size and overlap."
    )
    
    chunk_size = 384
    chunk_overlap = 75
    
    if chunking_strategy == "Custom":
        st.subheader("Custom Chunking Parameters")
        chunk_size = st.number_input(
            "Chunk Size (tokens):",
            min_value=1,
            value=384,
            step=1,
            help="Maximum number of tokens per chunk. Set any value you want. Smaller = more precise, Larger = more context."
        )
        chunk_overlap = st.number_input(
            "Chunk Overlap (tokens):",
            min_value=0,
            value=75,
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
    
    # Vector Store selection
    st.divider()
    st.header("💾 Vector Store Settings")
    vector_store_choice = st.radio(
        "Choose Vector Store:",
        ["FAISS", "OpenSearch"],
        help="FAISS: Local storage, fast, no cloud required. "
             "OpenSearch: Cloud storage, scalable, requires AWS OpenSearch domain."
    )
    
    opensearch_domain = None
    opensearch_index = None
    
    if vector_store_choice == "OpenSearch":
        # Get default domain from environment or use the working domain
        default_domain = os.getenv('AWS_OPENSEARCH_DOMAIN', 'intelycx-waseem-os')
        opensearch_domains = [
            "intelycx-waseem-os",  # Default working domain
            "intelycx-os-dev",
            "intelycx",
            "intelycx-os-demo",
            "intelycx-os-qa",
            "intelycx-os-common"
        ]
        # Find index of default domain, or use 0 if not found
        default_index = 0
        if default_domain in opensearch_domains:
            default_index = opensearch_domains.index(default_domain)
        opensearch_domain = st.selectbox(
            "OpenSearch Domain:",
            opensearch_domains,
            index=default_index,
            help="Select the OpenSearch domain to use for storing embeddings"
        )
        opensearch_index = st.text_input(
            "OpenSearch Index Name:",
            value="aris-rag-index",
            help="Name of the OpenSearch index (will be created if it doesn't exist)"
        )
        
        # Check if credentials are available
        import os
        from dotenv import load_dotenv
        load_dotenv()
        if not os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') or not os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'):
            st.error("⚠️ OpenSearch credentials not found in .env file. Please add AWS_OPENSEARCH_ACCESS_KEY_ID and AWS_OPENSEARCH_SECRET_ACCESS_KEY")
    else:
        st.info("💡 FAISS stores data locally in the 'vectorstore/' directory")
    
    st.divider()
    
    # Document upload
    st.header("📄 Upload Documents")
    uploaded_files = st.file_uploader(
        "Choose files",
        type=['pdf', 'txt', 'docx', 'doc'],
        accept_multiple_files=True,
        help="Upload PDF, TXT, or DOCX files"
    )
    
    if st.button("Process Documents", type="primary"):
        if uploaded_files:
            # Process documents (warnings shown above, but allow any values)
            process_uploaded_files(
                uploaded_files, use_cerebras, parser_preference,
                embedding_model, openai_model, cerebras_model,
                vector_store_choice.lower(), opensearch_domain, opensearch_index,
                chunk_size, chunk_overlap
            )
        else:
            st.warning("Please upload at least one document")
    
    st.divider()
    
    # Comprehensive Metrics Dashboard
    st.header("📊 R&D Metrics & Analytics")
    
    if st.session_state.documents_processed and st.session_state.rag_system:
        # Get all metrics
        all_metrics = st.session_state.metrics_collector.get_all_metrics()
        processing_stats = all_metrics.get('processing', {})
        query_stats = all_metrics.get('queries', {})
        parser_comparison = all_metrics.get('parser_comparison', {})
        
        # Model Information
        st.subheader("🤖 Current Models")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.info(f"**Embedding:**\n{st.session_state.rag_system.embedding_model}")
        with col2:
            if st.session_state.rag_system.use_cerebras:
                st.info(f"**LLM:**\n{st.session_state.rag_system.cerebras_model}")
            else:
                st.info(f"**LLM:**\n{st.session_state.rag_system.openai_model}")
        with col3:
            api_name = "Cerebras" if st.session_state.rag_system.use_cerebras else "OpenAI"
            st.info(f"**API:**\n{api_name}")
        with col4:
            vector_store_type = getattr(st.session_state.rag_system, 'vector_store_type', 'faiss')
            store_display = vector_store_type.upper()
            if vector_store_type == "opensearch":
                domain = getattr(st.session_state.rag_system, 'opensearch_domain', 'N/A')
                store_display += f"\n({domain})"
            st.info(f"**Vector Store:**\n{store_display}")
        with col5:
            chunk_size = getattr(st.session_state.rag_system, 'chunk_size', 384)
            chunk_overlap = getattr(st.session_state.rag_system, 'chunk_overlap', 75)
            st.info(f"**Chunking:**\n{chunk_size} tokens\n({chunk_overlap} overlap)")
        
        # Basic Stats
        st.subheader("📈 Overview")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Documents", processing_stats.get('total_documents', 0))
        with col2:
            st.metric("Chunks", processing_stats.get('total_chunks', 0))
        with col3:
            st.metric("Total Tokens", f"{processing_stats.get('total_tokens', 0):,}")
        with col4:
            st.metric("Queries", query_stats.get('total_queries', 0))
        
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
        if st.session_state.rag_system and st.session_state.rag_system.vectorstore:
            st.subheader("🔢 Token Analysis")
            chunk_stats = st.session_state.rag_system.get_chunk_token_stats()
            
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
    else:
        st.info("⏳ No documents processed yet. Upload and process documents to see metrics.")
    
    # Clear button
    if st.button("Clear All", type="secondary"):
        st.session_state.rag_system = None
        st.session_state.documents_processed = False
        st.session_state.chat_history = []
        st.session_state.processing_results = []
        st.session_state.document_processor = None
        st.session_state.metrics_collector.clear()
        st.rerun()

# Main content area
if st.session_state.documents_processed and st.session_state.rag_system:
    st.header("💬 Ask Questions")
    
    # Display chat history
    for i, (question, answer, sources) in enumerate(st.session_state.chat_history):
        with st.chat_message("user"):
            st.write(question)
        
        with st.chat_message("assistant"):
            st.write(answer)
            if sources:
                with st.expander("📎 Sources"):
                    for source in sources:
                        st.write(f"- {source}")
    
    # Query input
    question = st.chat_input("Ask a question about your documents...")
    
    if question:
        # Add user question to chat
        st.chat_message("user").write(question)
        
        # Get answer with improved accuracy settings
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Use improved accuracy settings: more chunks, MMR for diversity
                result = st.session_state.rag_system.query_with_rag(question, k=6, use_mmr=True)
                answer = result["answer"]
                sources = result.get("sources", [])
                num_chunks = result.get("num_chunks_used", 0)
                
                st.write(answer)
                
                # Show accuracy metrics and token counts
                if num_chunks > 0:
                    context_tokens = result.get("context_tokens", 0)
                    response_tokens = result.get("response_tokens", 0)
                    total_tokens = result.get("total_tokens", 0)
                    
                    st.caption(
                        f"📊 Used {num_chunks} relevant chunks | "
                        f"🔢 Tokens: {context_tokens:,} (context) + {response_tokens:,} (response) = {total_tokens:,} total"
                    )
                
                # Show sources
                if sources:
                    with st.expander("📎 Sources"):
                        for source in sources:
                            st.write(f"- {source}")
                        
                        # Show context chunks with more detail
                        if "context_chunks" in result:
                            with st.expander("🔍 Context Chunks Used"):
                                for i, chunk in enumerate(result["context_chunks"], 1):
                                    st.text_area(f"Chunk {i} (used in answer)", chunk, height=120, key=f"chunk_{i}_{len(st.session_state.chat_history)}")
        
        # Add to chat history
        st.session_state.chat_history.append((question, answer, sources))
        st.rerun()
    
else:
    st.info("👆 Please upload and process documents using the sidebar to start asking questions.")
    
    # Instructions
    with st.expander("📖 How to use"):
        st.markdown("""
        ### Steps:
        1. **Choose API**: Select OpenAI or Cerebras in the sidebar
        2. **Choose Parser**: Select parser (PyMuPDF recommended for speed)
        3. **Upload Documents**: Click "Browse files" and select your PDF, TXT, or DOCX files
        4. **Process**: Click "Process Documents" button
        5. **Ask Questions**: Once processed, type your questions in the chat input
        
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
        """)
