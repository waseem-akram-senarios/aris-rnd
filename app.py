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
                          embedding_model, openai_model, cerebras_model):
    """Process uploaded files with real-time progress tracking"""
    if not uploaded_files:
        return False
    
    # Initialize or update RAG system
    # Recreate if API, models, or embedding model changed
    needs_reinit = (
        st.session_state.rag_system is None or
        (hasattr(st.session_state.rag_system, 'use_cerebras') and st.session_state.rag_system.use_cerebras != use_cerebras) or
        (hasattr(st.session_state.rag_system, 'embedding_model') and st.session_state.rag_system.embedding_model != embedding_model) or
        (hasattr(st.session_state.rag_system, 'openai_model') and st.session_state.rag_system.openai_model != openai_model) or
        (hasattr(st.session_state.rag_system, 'cerebras_model') and st.session_state.rag_system.cerebras_model != cerebras_model)
    )
    
    if needs_reinit:
        st.session_state.rag_system = RAGSystem(
            use_cerebras=use_cerebras,
            metrics_collector=st.session_state.metrics_collector,
            embedding_model=embedding_model,
            openai_model=openai_model,
            cerebras_model=cerebras_model
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
                
                def progress_callback(status, progress):
                    progress_bar.progress(progress)
                    status_messages = {
                        'parsing': '🔍 Parsing document...',
                        'chunking': f'✂️ Chunking text... ({int(progress*100)}%)',
                        'embedding': f'🧮 Creating embeddings... ({int(progress*100)}%)',
                        'complete': '✅ Complete!',
                        'failed': '❌ Failed',
                        'processing': '⏳ Processing...'
                    }
                    message = status_messages.get(status, f'Processing... ({int(progress*100)}%)')
                    # Add special message for Docling
                    if parser_preference and parser_preference.lower() == 'docling' and status == 'parsing':
                        message = '🔍 Docling parsing (5-10 min, processing all pages)...'
                    # Add more detailed messages for chunking/embedding
                    elif status == 'chunking':
                        message = f'✂️ Chunking text... ({int(progress*100)}%) - This may take a few minutes for large documents'
                    elif status == 'embedding':
                        message = f'🧮 Creating embeddings... ({int(progress*100)}%) - This may take a few minutes for large documents'
                    status_text.text(message)
                
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
        ["Auto (Recommended)", "PyMuPDF", "Docling", "Textract"],
        help="Auto will try parsers in order: PyMuPDF → Docling → Textract. "
             "PyMuPDF is fast for text-based PDFs. "
             "Docling extracts the most content (processes all pages) but takes 5-10 minutes. "
             "Textract requires AWS credentials and is best for scanned PDFs."
    )
    parser_preference = None if parser_choice == "Auto (Recommended)" else parser_choice.lower()
    
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
            process_uploaded_files(uploaded_files, use_cerebras, parser_preference,
                                 embedding_model, openai_model, cerebras_model)
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
        col1, col2, col3 = st.columns(3)
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
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Chunks", f"{chunk_stats['total_chunks']:,}")
                with col2:
                    st.metric(
                        "Avg Tokens/Chunk",
                        f"{chunk_stats['avg_tokens_per_chunk']:.1f}"
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
                
                # Token distribution histogram
                if chunk_stats['chunk_token_counts']:
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
                        
                        # Show token count ranges
                        ranges = {
                            '0-100': sum(1 for t in token_counts if 0 <= t <= 100),
                            '101-200': sum(1 for t in token_counts if 101 <= t <= 200),
                            '201-300': sum(1 for t in token_counts if 201 <= t <= 300),
                            '301-384': sum(1 for t in token_counts if 301 <= t <= 384),
                            '385+': sum(1 for t in token_counts if t > 384)
                        }
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
        2. **Choose Parser**: Select parser (Auto recommended for best results)
        3. **Upload Documents**: Click "Browse files" and select your PDF, TXT, or DOCX files
        4. **Process**: Click "Process Documents" button
        5. **Ask Questions**: Once processed, type your questions in the chat input
        
        ### Supported Formats:
        - PDF files (.pdf) - Uses PyMuPDF, Docling, or Textract
        - Text files (.txt)
        - Word documents (.docx, .doc)
        
        ### Parser Options:
        - **Auto**: Automatically selects best parser (PyMuPDF → Docling → Textract)
        - **PyMuPDF**: Fast parser for text-based PDFs (recommended for speed)
        - **Docling**: Extracts the most content, processes all pages automatically. Takes 5-10 minutes but extracts more text than PyMuPDF
        - **Textract**: AWS OCR for scanned/image PDFs (requires AWS credentials)
        
        ### Features:
        - Token-aware chunking (512 tokens per chunk)
        - Real-time processing with progress tracking
        - Source attribution
        """)
