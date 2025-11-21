"""
RAG System for document processing and querying
"""
import os
import time
import logging
from typing import List, Dict, Optional, Callable
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document
import requests
from utils.tokenizer import TokenTextSplitter

load_dotenv()

class RAGSystem:
    def __init__(self, use_cerebras=False, metrics_collector=None, 
                 embedding_model="text-embedding-3-small",
                 openai_model="gpt-3.5-turbo",
                 cerebras_model="llama3.1-8b"):
        self.use_cerebras = use_cerebras
        
        # Store model selections
        self.embedding_model = embedding_model
        self.openai_model = openai_model
        self.cerebras_model = cerebras_model
        
        # Use selected embedding model
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=embedding_model
        )
        self.vectorstore = None
        # Use token-aware text splitter with smaller chunks for better accuracy
        self.text_splitter = TokenTextSplitter(
            chunk_size=384,  # Smaller chunks for more precise retrieval (was 512)
            chunk_overlap=75,  # Increased overlap for better context continuity (was 50)
            model_name=embedding_model
        )
        
        # Document tracking for incremental updates
        self.document_index: Dict[str, List[int]] = {}  # {doc_id: [chunk_indices]}
        self.total_tokens = 0
        
        # Metrics collector for R&D analytics
        self.metrics_collector = metrics_collector
        
        # Initialize LLM
        if use_cerebras:
            self.llm = None  # Will use Cerebras API directly
            self.cerebras_api_key = os.getenv('CEREBRAS_API_KEY')
        else:
            self.llm = None  # Will use OpenAI API directly
            self.openai_api_key = os.getenv('OPENAI_API_KEY')
    
    def process_documents(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None):
        """Process and chunk documents, then create vector store"""
        logger = logging.getLogger(__name__)
        
        # Validate inputs
        if not texts:
            return 0
        
        # Create Document objects
        documents = []
        for i, text in enumerate(texts):
            # Safely get metadata - handle case where metadatas list is shorter than texts
            if metadatas and i < len(metadatas):
                metadata = metadatas[i] if isinstance(metadatas[i], dict) else {}
            else:
                metadata = {}
            
            # Ensure text is a string and not None
            if text is None:
                text = ""
            if not isinstance(text, str):
                text = str(text)
            
            # Skip empty documents
            if not text.strip():
                continue
            
            documents.append(Document(page_content=text, metadata=metadata))
        
        # Validate we have documents to process
        if not documents:
            return 0
        
        # Split documents into chunks using token-aware splitter
        logger.info(f"Starting chunking for {len(documents)} document(s), total text length: {sum(len(doc.page_content) for doc in documents):,} chars")
        if progress_callback:
            progress_callback('chunking', 0.1)
        
        try:
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"Chunking completed: {len(chunks)} chunks created")
        except Exception as e:
            logger.error(f"Chunking failed: {str(e)}")
            raise ValueError(f"Failed to split documents into chunks: {str(e)}")
        
        # Validate chunks
        if not chunks:
            raise ValueError("No chunks created from documents. The documents may be empty or too small.")
        
        if progress_callback:
            progress_callback('chunking', 0.3)
        
        # Filter out invalid chunks
        valid_chunks = []
        for chunk in chunks:
            if chunk is None:
                continue
            if not hasattr(chunk, 'page_content'):
                continue
            if not chunk.page_content or not chunk.page_content.strip():
                continue
            valid_chunks.append(chunk)
        
        if not valid_chunks:
            raise ValueError("No valid chunks created. All chunks are empty or invalid.")
        
        logger.info(f"Valid chunks: {len(valid_chunks)}/{len(chunks)}")
        
        if progress_callback:
            progress_callback('chunking', 0.5)
        
        # Track tokens
        for chunk in valid_chunks:
            token_count = chunk.metadata.get('token_count', 0)
            self.total_tokens += token_count
        
        logger.info(f"Total tokens: {self.total_tokens:,}")
        
        if progress_callback:
            progress_callback('embedding', 0.6)
        
        # Create or update vector store incrementally
        logger.info(f"Creating/updating vector store with {len(valid_chunks)} chunks...")
        try:
            if self.vectorstore is None:
                # Validate chunks before creating vectorstore
                if len(valid_chunks) == 0:
                    raise ValueError("Cannot create vectorstore: no valid chunks")
                logger.info(f"Creating new FAISS vectorstore with {len(valid_chunks)} chunks (this may take a few minutes for large documents)...")
                self.vectorstore = FAISS.from_documents(valid_chunks, self.embeddings)
                logger.info("Vectorstore created successfully")
            else:
                # Add to existing vector store (incremental update)
                if len(valid_chunks) > 0:
                    logger.info(f"Adding {len(valid_chunks)} chunks to existing vectorstore (this may take a few minutes for large documents)...")
                    self.vectorstore.add_documents(valid_chunks)
                    logger.info("Chunks added to vectorstore successfully")
        except Exception as e:
            logger.error(f"Vectorstore creation/update failed: {str(e)}")
            raise ValueError(f"Failed to create/update vectorstore: {str(e)}. This may be due to empty chunks or embedding issues.")
        
        if progress_callback:
            progress_callback('embedding', 0.9)
        
        # Track document chunks
        # Calculate chunk_start based on total existing chunks
        chunk_start = sum(len(chunk_list) for chunk_list in self.document_index.values())
        for i, chunk in enumerate(valid_chunks):
            doc_id = chunk.metadata.get('source', f'doc_{len(documents)}')
            if doc_id not in self.document_index:
                self.document_index[doc_id] = []
            self.document_index[doc_id].append(chunk_start + i)
        
        logger.info(f"Document indexing completed: {len(valid_chunks)} chunks indexed")
        
        return len(valid_chunks)
    
    def add_documents_incremental(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None) -> Dict:
        """
        Add documents incrementally to the vector store.
        Returns processing statistics.
        
        Args:
            texts: List of text content
            metadatas: List of metadata dictionaries
            progress_callback: Optional callback function(status, progress) for updates
        
        Returns:
            Dict with processing stats: chunks_created, tokens_added, documents_added
        """
        chunks_before = sum(len(chunks) for chunks in self.document_index.values())
        tokens_before = self.total_tokens
        
        chunks_created = self.process_documents(texts, metadatas, progress_callback=progress_callback)
        
        chunks_after = sum(len(chunks) for chunks in self.document_index.values())
        tokens_after = self.total_tokens
        
        return {
            'chunks_created': chunks_created,
            'tokens_added': tokens_after - tokens_before,
            'documents_added': len(texts),
            'total_chunks': chunks_after,
            'total_tokens': tokens_after
        }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the tokenizer."""
        return self.text_splitter.count_tokens(text)
    
    def _clean_answer(self, answer: str) -> str:
        """
        Clean answer to remove repetitive text, greetings, and unwanted endings.
        
        Args:
            answer: Raw answer from LLM
        
        Returns:
            Cleaned answer
        """
        if not answer:
            return answer
        
        # Remove common unwanted endings
        unwanted_endings = [
            "Best regards",
            "Thank you",
            "Please let me know",
            "If you have any other questions",
            "I will be happy to help",
            "I will do my best to help",
            "[Your Name]",
            "Best regards, [Your Name]",
            "Thank you, [Your Name]"
        ]
        
        # Find and remove unwanted endings
        lines = answer.split('\n')
        cleaned_lines = []
        found_unwanted = False
        
        for line in lines:
            line_stripped = line.strip()
            # Check if this line contains unwanted text
            if any(unwanted in line_stripped for unwanted in unwanted_endings):
                found_unwanted = True
                break  # Stop at first unwanted ending
            cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines).strip()
        
        # Remove repetitive "Best regards" patterns
        import re
        # Remove multiple occurrences of "Best regards" patterns
        cleaned = re.sub(r'(Best regards[,\s]*\[Your Name\]\s*)+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(Best regards\s*)+', '', cleaned, flags=re.IGNORECASE)
        
        # Remove trailing repetitive phrases
        cleaned = re.sub(r'(\s*Best regards[,\s]*\[Your Name\]\s*)+$', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
        
        return cleaned.strip()
    
    def query_with_rag(self, question: str, k: int = 6, use_mmr: bool = True) -> Dict:
        """
        Query the RAG system with improved accuracy.
        
        Args:
            question: The question to answer
            k: Number of chunks to retrieve (default 6 for better coverage)
            use_mmr: Use Maximum Marginal Relevance for diverse, relevant chunks
        
        Returns:
            Dict with answer, sources, and context chunks
        """
        query_start_time = time.time()
        
        if self.vectorstore is None:
            return {
                "answer": "No documents have been uploaded yet. Please upload documents first.",
                "sources": []
            }
        
        # Retrieve relevant documents with MMR for better diversity and relevance
        if use_mmr:
            # Use MMR to get diverse but relevant chunks
            retriever = self.vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs={
                    "k": k,
                    "fetch_k": min(k * 3, 20),  # Fetch more candidates for MMR
                    "lambda_mult": 0.5  # Balance diversity (0.5 = balanced)
                }
            )
        else:
            # Standard similarity search
            retriever = self.vectorstore.as_retriever(search_kwargs={"k": k})
        
        # Use invoke for newer LangChain versions, fallback to get_relevant_documents
        try:
            relevant_docs = retriever.invoke(question)
        except AttributeError:
            # Fallback for older versions
            relevant_docs = retriever.get_relevant_documents(question)
        
        # Build context with metadata for better accuracy
        context_parts = []
        for i, doc in enumerate(relevant_docs, 1):
            # Add source and page info if available
            source = doc.metadata.get('source', 'Unknown')
            page = doc.metadata.get('source_page', doc.metadata.get('page', ''))
            page_info = f" (Page {page})" if page else ""
            
            context_parts.append(f"[Source {i}: {source}{page_info}]\n{doc.page_content}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Count tokens in context (question + context)
        context_tokens = self.count_tokens(question + "\n\n" + context)
        
        # Generate answer using LLM with improved prompt
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras(question, context, relevant_docs)
        else:
            answer, response_tokens = self._query_openai(question, context, relevant_docs)
        
        response_time = time.time() - query_start_time
        total_tokens = context_tokens + response_tokens
        
        # Record query metrics
        if self.metrics_collector:
            self.metrics_collector.record_query(
                question=question,
                answer_length=len(answer),
                response_time=response_time,
                chunks_used=len(relevant_docs),
                sources_count=len(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
                api_used="cerebras" if self.use_cerebras else "openai",
                success=True,
                context_tokens=context_tokens,
                response_tokens=response_tokens,
                total_tokens=total_tokens
            )
        
        return {
            "answer": answer,
            "sources": list(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
            "context_chunks": [doc.page_content[:300] + "..." for doc in relevant_docs],
            "num_chunks_used": len(relevant_docs),
            "response_time": response_time,
            "context_tokens": context_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens
        }
    
    def _query_openai(self, question: str, context: str, relevant_docs: List = None) -> tuple:
        """
        Query OpenAI with improved prompt for accuracy.
        
        Args:
            question: The question to answer
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
        """
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Improved prompt for accuracy - prevents hallucinations and repetitive text
        system_prompt = """You are a precise technical assistant that provides accurate, detailed answers based strictly on the provided context. 

CRITICAL RULES:
- Answer ONLY using information from the provided context
- DO NOT add greetings, signatures, or closing statements
- DO NOT repeat phrases or sentences
- DO NOT include "Best regards", "Thank you", or similar endings
- DO NOT make up information not in the context
- Be specific and cite exact values, measurements, and specifications when available
- If information is not in the context, explicitly state "The provided context does not contain this information"
- Include relevant details like dimensions, materials, standards, and procedures
- Maintain technical accuracy and precision
- If multiple sources provide information, synthesize them clearly
- End your answer when you have provided the information - do not add unnecessary text"""
        
        user_prompt = f"""Context from documents:
{context}

Question: {question}

Instructions:
1. Read the context carefully
2. Identify the most relevant information for the question
3. Provide a comprehensive, accurate answer using ONLY information from the context
4. Include specific details, numbers, and specifications when available
5. If the answer is not in the context, state so clearly
6. DO NOT add greetings, signatures, or closing statements
7. DO NOT repeat information or phrases
8. Stop immediately after providing the answer

Answer:"""
        
        try:
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more accurate, deterministic answers
                max_tokens=800,  # Increased for more detailed answers
                stop=["Best regards", "Thank you", "Please let me know", "If you have any other questions"]  # Stop at common endings
            )
            # Check if response has choices
            if not response.choices or len(response.choices) == 0:
                raise ValueError("OpenAI API returned no choices in response")
            answer = response.choices[0].message.content
            if answer is None:
                raise ValueError("OpenAI API returned empty content in response")
            
            # Get token usage from response
            response_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            if response_tokens == 0:
                # Fallback: estimate tokens in answer
                response_tokens = self.count_tokens(answer)
            
            # Clean up any repetitive or unwanted endings
            answer = self._clean_answer(answer)
            return answer, response_tokens
        except Exception as e:
            error_msg = str(e)
            # Provide user-friendly error messages
            if "model_not_found" in error_msg or "404" in error_msg:
                if "gpt-5" in error_msg.lower():
                    error_answer = f"Error: GPT-5 requires organization verification and is not publicly available. Please use a different model like gpt-4o or gpt-4."
                elif "verify" in error_msg.lower():
                    error_answer = f"Error: This model requires organization verification. Please use a different model or verify your organization at https://platform.openai.com/settings/organization/general"
                else:
                    error_answer = f"Error: Model '{self.openai_model}' is not available. Please check if the model name is correct or try a different model."
            elif "401" in error_msg or "unauthorized" in error_msg.lower():
                error_answer = "Error: Invalid API key. Please check your OpenAI API key in the .env file."
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                error_answer = "Error: Rate limit exceeded. Please wait a moment and try again."
            else:
                error_answer = f"Error querying OpenAI: {error_msg}"
            return error_answer, self.count_tokens(error_answer)
    
    def _query_cerebras(self, question: str, context: str, relevant_docs: List = None) -> tuple:
        """Query Cerebras API with improved prompt for accuracy"""
        # Improved prompt for Cerebras
        prompt = f"""You are a precise technical assistant. Answer the question using ONLY information from the provided context. Be specific and accurate.

CRITICAL: DO NOT add greetings, signatures, or closing statements. DO NOT repeat phrases. End your answer when you have provided the information.

Context:
{context}

Question: {question}

Instructions:
- Use ONLY information from the context above
- Be specific with numbers, measurements, and technical details
- If information is not in the context, state "The context does not contain this information"
- Provide comprehensive and accurate answers
- DO NOT add "Best regards", "Thank you", or similar endings
- Stop immediately after providing the answer

Answer:"""
        
        headers = {
            "Authorization": f"Bearer {self.cerebras_api_key}",
            "Content-Type": "application/json"
        }
        
        # Use selected Cerebras model
        try:
            data = {
                "model": self.cerebras_model,
                "prompt": prompt,
                "max_tokens": 500,
                "temperature": 0.7
            }
            
            response = requests.post(
                "https://api.cerebras.ai/v1/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                choices = result.get('choices', [])
                if not choices or len(choices) == 0:
                    raise ValueError("Cerebras API returned no choices in response")
                answer = choices[0].get('text', 'No response generated')
                if not answer:
                    answer = 'No response generated'
                
                # Get token usage from response if available
                response_tokens = result.get('usage', {}).get('completion_tokens', 0)
                if response_tokens == 0:
                    # Fallback: estimate tokens in answer
                    response_tokens = self.count_tokens(answer)
                
                # Clean answer to remove unwanted text
                answer = self._clean_answer(answer)
                return answer, response_tokens
            else:
                error_msg = f"Error: Cerebras API returned status {response.status_code}"
                return error_msg, self.count_tokens(error_msg)
        except Exception as e:
            error_msg = f"Error: Could not get response from Cerebras API: {str(e)}"
            return error_msg, self.count_tokens(error_msg)
    
    def save_vectorstore(self, path: str = "vectorstore"):
        """Save vector store to disk"""
        if self.vectorstore:
            self.vectorstore.save_local(path)
            # Also save document index
            import pickle
            index_path = os.path.join(path, "document_index.pkl")
            with open(index_path, 'wb') as f:
                pickle.dump({
                    'document_index': self.document_index,
                    'total_tokens': self.total_tokens
                }, f)
    
    def load_vectorstore(self, path: str = "vectorstore"):
        """Load vector store from disk"""
        if os.path.exists(path):
            self.vectorstore = FAISS.load_local(path, self.embeddings, allow_dangerous_deserialization=True)
            # Also load document index
            import pickle
            index_path = os.path.join(path, "document_index.pkl")
            if os.path.exists(index_path):
                with open(index_path, 'rb') as f:
                    data = pickle.load(f)
                    self.document_index = data.get('document_index', {})
                    self.total_tokens = data.get('total_tokens', 0)
            return True
        return False
    
    def get_stats(self) -> Dict:
        """Get statistics about the RAG system."""
        total_documents = len(self.document_index)
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        
        # Estimate embedding cost (text-embedding-3-small: $0.02 per 1M tokens)
        estimated_cost = (self.total_tokens / 1_000_000) * 0.02
        
        return {
            'total_documents': total_documents,
            'total_chunks': total_chunks,
            'total_tokens': self.total_tokens,
            'estimated_embedding_cost_usd': estimated_cost
        }
    
    def get_chunk_token_stats(self) -> Dict:
        """
        Get token statistics for all chunks in the vectorstore.
        Uses metrics collector data if available, otherwise estimates from vectorstore.
        
        Returns:
            Dict with token distribution statistics
        """
        if self.vectorstore is None:
            return {
                'chunk_token_counts': [],
                'avg_tokens_per_chunk': 0,
                'min_tokens_per_chunk': 0,
                'max_tokens_per_chunk': 0,
                'total_chunks': 0
            }
        
        # Try to get chunk token counts from metrics collector first
        if self.metrics_collector and hasattr(self.metrics_collector, 'processing_metrics'):
            chunk_token_counts = []
            for metric in self.metrics_collector.processing_metrics:
                if metric.success and metric.chunks_created > 0:
                    # Estimate tokens per chunk (total tokens / chunks)
                    tokens_per_chunk = metric.tokens_extracted / metric.chunks_created if metric.chunks_created > 0 else 0
                    # Add tokens for each chunk (approximate)
                    for _ in range(metric.chunks_created):
                        chunk_token_counts.append(int(tokens_per_chunk))
            
            if chunk_token_counts:
                return {
                    'chunk_token_counts': chunk_token_counts,
                    'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                    'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                    'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                    'total_chunks': len(chunk_token_counts)
                }
        
        # Fallback: try to get from vectorstore directly
        try:
            # Access the underlying documents
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = self.vectorstore.docstore._dict
                chunk_token_counts = []
                
                # Extract token counts from document metadata
                for doc_id, doc in all_docs.items():
                    if hasattr(doc, 'metadata') and 'token_count' in doc.metadata:
                        chunk_token_counts.append(doc.metadata['token_count'])
                    elif hasattr(doc, 'page_content'):
                        # Fallback: count tokens from content
                        token_count = self.count_tokens(doc.page_content)
                        chunk_token_counts.append(token_count)
                
                if chunk_token_counts:
                    return {
                        'chunk_token_counts': chunk_token_counts,
                        'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                        'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                        'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                        'total_chunks': len(chunk_token_counts)
                    }
        except Exception:
            pass
        
        # Final fallback: estimate from total tokens and chunks
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        if total_chunks > 0 and self.total_tokens > 0:
            avg_tokens = self.total_tokens / total_chunks
            # Create a distribution estimate
            estimated_counts = [int(avg_tokens)] * total_chunks
            return {
                'chunk_token_counts': estimated_counts,
                'avg_tokens_per_chunk': avg_tokens,
                'min_tokens_per_chunk': int(avg_tokens * 0.8),  # Estimate
                'max_tokens_per_chunk': int(avg_tokens * 1.2),  # Estimate
                'total_chunks': total_chunks
            }
        
        # Return empty stats if nothing works
        return {
            'chunk_token_counts': [],
            'avg_tokens_per_chunk': 0,
            'min_tokens_per_chunk': 0,
            'max_tokens_per_chunk': 0,
            'total_chunks': 0
        }

