"""
Agentic RAG synthesis with query decomposition and multi-source merging.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import os
import logging
import time as time_module
import requests
from typing import List, Dict, Optional

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class AgenticRAGMixin:
    """Mixin providing agentic rag synthesis with query decomposition and multi-source merging capabilities."""
    
    def _synthesize_agentic_results(
        self,
        question: str,
        sub_queries: List[str],
        relevant_docs: List,
        query_start_time: float,
        model: str = None
    ) -> Dict:
        """
        Synthesize results from multiple sub-queries using LLM.
        
        Args:
            question: Original question
            sub_queries: List of sub-queries used for retrieval
            relevant_docs: Retrieved document chunks
            query_start_time: Start time for query (for metrics)
        
        Returns:
            Dict with answer, sources, citations, etc.
        """
        # Build context with metadata
        context_parts = []
        citations = []
        
        # Try to get similarity scores if available (for ranking)
        doc_scores = {}
        doc_order_scores = {}  # Use retrieval order as proxy for relevance when scores unavailable
        
        # First, try to get scores using similarity_search_with_score directly
        try:
            if hasattr(self.vectorstore, 'similarity_search_with_score'):
                # Get more results to ensure we have scores for all retrieved docs
                scored_docs = self.vectorstore.similarity_search_with_score(question, k=max(len(relevant_docs) * 2, 20))
                
                # Create a mapping of document content to scores
                for scored_doc, score in scored_docs:
                    if hasattr(scored_doc, 'page_content'):
                        # Use first 200 chars for better matching (more unique than 100)
                        doc_content = scored_doc.page_content[:200]
                        # Also try matching by full content hash
                        import hashlib
                        content_hash = hashlib.md5(scored_doc.page_content.encode('utf-8')).hexdigest()
                        score_val = float(score) if score is not None else 0.0
                        doc_scores[doc_content] = score_val
                        doc_scores[content_hash] = score_val
        except Exception as e:
            logger.debug(f"Could not retrieve similarity scores for agentic RAG: {e}")
        
        # Use retrieval order as a proxy for relevance (earlier = more relevant)
        for idx, doc in enumerate(relevant_docs):
            # Normalize order score: first doc = 1.0, last = 0.0
            order_score = 1.0 - (idx / max(len(relevant_docs), 1))
            if hasattr(doc, 'page_content'):
                doc_content = doc.page_content[:200]
                import hashlib
                content_hash = hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()
                doc_order_scores[doc_content] = order_score
                doc_order_scores[content_hash] = order_score
        
        for i, doc in enumerate(relevant_docs, 1):
            import re
            
            # Extract citation metadata - use helper method for consistent extraction
            chunk_text = doc.page_content
            
            # Validate document has metadata before extraction
            if not hasattr(doc, 'metadata') or not doc.metadata:
                logger.warning(f"Document at index {i} missing metadata during citation creation (Agentic RAG)")
                doc.metadata = {}
            
            # Build UI config from current state
            ui_config = getattr(self, 'ui_config', {
                'temperature': ARISConfig.DEFAULT_TEMPERATURE,
                'max_tokens': ARISConfig.DEFAULT_MAX_TOKENS,
                'active_sources': self.active_sources
            })
            
            # Extract source with confidence score
            source, source_confidence = self._extract_source_from_chunk(doc, chunk_text, None, ui_config=ui_config)
            
            # Validate source was extracted successfully
            if not source or source == 'Unknown':
                logger.warning(f"Could not extract valid source for citation {i} (Agentic RAG). Chunk preview: {chunk_text[:100]}...")
            
            # Extract page number with confidence score
            # First, check if ingestion already computed a high-confidence page assignment
            ingestion_page = doc.metadata.get('page')
            ingestion_confidence = doc.metadata.get('page_confidence')
            ingestion_method = doc.metadata.get('page_extraction_method')
            
            if (ingestion_page is not None and ingestion_confidence is not None 
                    and float(ingestion_confidence) >= 0.7):
                page = int(ingestion_page)
                page_confidence = float(ingestion_confidence)
            else:
                page, page_confidence = self._extract_page_number(doc, chunk_text)
            
            # Ensure page is always set (fallback to 1 if None)
            if page is None:
                page = 1
                page_confidence = 0.1
                source_name = doc.metadata.get('source', 'Unknown')
                logger.warning(f"Agentic RAG Citation {i}: page was None, using fallback page 1. Source: {source_name}")
            
            start_char = doc.metadata.get('start_char', None)
            end_char = doc.metadata.get('end_char', None)
            
            image_ref = None
            image_info = None
            page_blocks = doc.metadata.get('page_blocks', [])
            
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'image':
                        if page and block.get('page') == page:
                            image_ref = {
                                'page': block.get('page'),
                                'image_index': block.get('image_index'),
                                'bbox': block.get('bbox'),
                                'xref': block.get('xref')
                            }
                            image_info = f"Image {block.get('image_index', '?')} on Page {page}"
                            break
            
            if not image_ref:
                if doc.metadata.get('has_image') or doc.metadata.get('image_index') is not None:
                    image_ref = {
                        'page': page,
                        'image_index': doc.metadata.get('image_index'),
                        'bbox': doc.metadata.get('image_bbox')
                    }
                    image_info = f"Image {doc.metadata.get('image_index', '?')} on Page {page}"  # page is always set (>= 1)
            
            # Generate context-aware snippet using original question
            # ENHANCEMENT: Pass query language to prefer English text for English queries (fixes QA citation language mismatch)
            query_language = self.ui_config.get('query_language', None)
            snippet_clean = self._generate_context_snippet(
                chunk_text, question, max_length=500,
                query_language=query_language, doc_metadata=doc.metadata
            )
            
            # Build source location - page is always guaranteed to be set (>= 1) at this point
            source_location_parts = [f"Page {page}"]  # Always include page
            
            # Only add image info if this specific chunk has an image reference
            if image_ref:
                # This chunk is actually associated with an image
                image_index = image_ref.get('image_index', '?')
                source_location_parts.append(f"Image {image_index}")
            elif doc.metadata.get('has_image') and doc.metadata.get('image_index') is not None:
                # Chunk metadata indicates it has an image reference
                image_index = doc.metadata.get('image_index', '?')
                source_location_parts.append(f"Image {image_index}")
            # REMOVED: Don't use document-level images_detected - it's too broad and misleading
            
            source_location = " | ".join(source_location_parts)  # Always includes "Page X"
            
            # Extract section/heading information from page_blocks if available
            section = None
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'heading':
                        section = block.get('text', '')
                        break
            
            # Determine extraction method based on confidence scores
            extraction_method = 'metadata' if source_confidence >= 0.7 else ('text_marker' if source_confidence >= 0.3 else 'fallback')
            
            # Get similarity score if available (for ranking)
            similarity_score = None
            doc_content_key = chunk_text[:200] if chunk_text else ""
            import hashlib
            content_hash = hashlib.md5(chunk_text.encode('utf-8')).hexdigest() if chunk_text else ""
            
            # Try multiple matching strategies
            if doc_content_key in doc_scores:
                similarity_score = doc_scores[doc_content_key]
            elif content_hash in doc_scores:
                similarity_score = doc_scores[content_hash]
            # Use order-based score as fallback
            elif doc_content_key in doc_order_scores:
                # Convert order score to similarity-like score (0.5 to 1.0 range)
                order_score = doc_order_scores[doc_content_key]
                similarity_score = 0.5 + (order_score * 0.5)  # Map 0.0-1.0 order to 0.5-1.0 similarity
            elif content_hash in doc_order_scores:
                order_score = doc_order_scores[content_hash]
                similarity_score = 0.5 + (order_score * 0.5)
            # Also try to get from metadata if stored there
            elif hasattr(doc, 'metadata') and 'similarity_score' in doc.metadata:
                similarity_score = doc.metadata.get('similarity_score')
            
            # Ensure page is always set (fallback to 1 if None) - double check for agentic RAG
            if page is None:
                page = 1
                page_confidence = 0.1
                source_name = doc.metadata.get('source', 'Unknown')
                logger.warning(f"Agentic RAG Citation {i}: page was None in citation dict, using fallback page 1. Source: {source_name}")
            
            # Get page_extraction_method from chunk metadata
            # Use ingestion-stored method if available, otherwise infer from page_confidence
            page_extraction_method = doc.metadata.get('page_extraction_method', None)
            if not page_extraction_method or page_extraction_method == 'unknown':
                if page_confidence >= 0.98:
                    page_extraction_method = 'text_marker'
                elif page_confidence >= 0.85:
                    page_extraction_method = 'metadata'
                elif page_confidence >= 0.75:
                    page_extraction_method = 'image_metadata'
                elif page_confidence >= 0.3:
                    page_extraction_method = 'heuristic'
                elif page_confidence >= 0.1:
                    page_extraction_method = 'fallback'
                else:
                    page_extraction_method = 'unknown'
            
            # Extract image_number from image_ref, metadata, OR text patterns (agentic RAG)
            image_number = None
            
            # PRIORITY 1: Check metadata sources
            if image_ref and isinstance(image_ref, dict):
                image_number = image_ref.get('image_index') or image_ref.get('image_number')
            
            if image_number is None and doc.metadata.get('image_index') is not None:
                image_number = doc.metadata.get('image_index')
            
            if image_number is None and doc.metadata.get('image_number') is not None:
                image_number = doc.metadata.get('image_number')
            
            # PRIORITY 2: Extract from text patterns (for OCR content)
            if image_number is None and chunk_text:
                import re
                # Pattern: "Image X on Page Y" or "IMAGE X" or "Figure X"
                image_text_match = re.search(r'(?:Image|IMAGE|Imagen|Fig(?:ure)?|FIGURE)\s*[#:]?\s*(\d+)', chunk_text[:500])
                if image_text_match:
                    image_number = int(image_text_match.group(1))
                    logger.debug(f"Agentic RAG Citation {i}: Extracted image number {image_number} from text pattern")
            elif doc.metadata.get('image_number') is not None:
                image_number = doc.metadata.get('image_number')
            
            # Check if this is image-derived content (for content_type only)
            # NOTE: We don't show specific image numbers as they're misleading
            is_image_content = (image_number is not None) or (image_ref is not None) or ('<!-- image -->' in chunk_text)
            
            # Build source_location - just show Page number
            source_location = f"Page {page}"
            
            citation = {
                'id': i,
                'source': source if source and source != 'Unknown' else 'Unknown',
                'document_id': doc.metadata.get('document_id', None),  # Unique document identifier
                'source_confidence': source_confidence,
                'page': page,  # Always guaranteed to be an integer >= 1
                'image_number': None,  # Don't show misleading sequential image numbers
                'page_confidence': page_confidence,
                'page_extraction_method': page_extraction_method,  # How page was determined
                'section': section,
                'snippet': snippet_clean,
                'full_text': chunk_text,
                'similarity_score': similarity_score,  # Vector similarity score for ranking
                'start_char': start_char,
                'end_char': end_char,
                'chunk_index': doc.metadata.get('chunk_index', None),
                'image_ref': {'page': page, 'has_image': True} if is_image_content else image_ref,
                'image_info': f"Image content on Page {page}" if is_image_content else image_info,
                'source_location': source_location,
                'content_type': 'image' if is_image_content else 'text',
                'extraction_method': extraction_method
            }
            citations.append(citation)
            logger.debug(f"Agentic RAG Citation {i}: source='{source}', page={page}, is_image={is_image_content}, method={page_extraction_method}")
            
            page_info = f" (Page {page})"  # page is always set
            context_parts.append(f"[Source {i}: {source}{page_info}]\n{chunk_text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Count tokens
        context_tokens = self.count_tokens(question + "\n\n" + context)
        
        # Generate answer using synthesis prompt
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras_agentic(question, sub_queries, context, relevant_docs, model=model)
        else:
            if not self.openai_api_key:
                answer, response_tokens = self._query_offline(question, context, relevant_docs)
            else:
                answer, response_tokens = self._query_openai_agentic(question, sub_queries, context, relevant_docs, model=model)
        
        response_time = time_module.time() - query_start_time
        total_tokens = context_tokens + response_tokens
        
        # Deduplicate and rank citations
        if citations:
            citations = self._deduplicate_citations(citations)
            citations = self._rank_citations_by_relevance(citations, question)
        
        # Record metrics
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
        
        # FIX: Only include sources that have citations (filtered sources)
        citation_sources = list(set([c.get('source', 'Unknown') for c in citations if c.get('source')]))
        if not citation_sources:
            citation_sources = list(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs]))
        
        return {
            "answer": answer,
            "sources": citation_sources,  # Only sources with citations
            "context_chunks": [doc.page_content for doc in relevant_docs],
            "citations": citations,
            "num_chunks_used": len(relevant_docs),
            "response_time": response_time,
            "context_tokens": context_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "sub_queries": sub_queries  # Include sub-queries in response for UI display
        }
    
    def _query_openai_agentic(
        self,
        question: str,
        sub_queries: List[str],
        context: str,
        relevant_docs: List = None,
        model: str = None
    ) -> tuple:
        """
        Query OpenAI with Agentic RAG synthesis prompt.
        
        Args:
            question: Original question
            sub_queries: List of sub-queries analyzed
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
        
        Returns:
            Tuple of (answer, response_tokens)
        """
        from openai import OpenAI
        from shared.config.settings import ARISConfig
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Select target model
        target_model = model or self.openai_model or ARISConfig.OPENAI_MODEL
        
        # Truncate context if it exceeds model's token limit
        MAX_CONTEXT_TOKENS = 100000  # Reserve ~28k for prompt, question, and response
        context_tokens = self.count_tokens(context)
        
        if context_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(
                f"Agentic RAG: Context too large ({context_tokens:,} tokens > {MAX_CONTEXT_TOKENS:,} limit). "
                f"Truncating to fit within model limits..."
            )
            
            # Intelligent truncation: preserve important sections
            image_section_start = context.find('IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)')
            image_section_end = context.find('\n\n---\n\n', image_section_start + 100) if image_section_start >= 0 else -1
            
            question_tokens = self.count_tokens(question)
            sub_queries_tokens = sum(self.count_tokens(sq) for sq in sub_queries)
            system_prompt_estimate = 800  # Rough estimate for agentic system prompt
            buffer_tokens = 2000  # Safety buffer
            available_context_tokens = MAX_CONTEXT_TOKENS - question_tokens - sub_queries_tokens - system_prompt_estimate - buffer_tokens
            
            if image_section_start >= 0 and image_section_end >= 0:
                image_section = context[image_section_start:image_section_end]
                image_section_tokens = self.count_tokens(image_section)
                remaining_tokens = available_context_tokens - image_section_tokens
                
                if remaining_tokens > 0:
                    main_context = context[:image_section_start]
                    truncated_main = self._truncate_text_by_tokens(main_context, remaining_tokens)
                    context = truncated_main + "\n\n" + image_section
                    logger.info(f"Agentic RAG: Preserved image section ({image_section_tokens:,} tokens), truncated main context to {remaining_tokens:,} tokens")
                else:
                    context = self._truncate_text_by_tokens(context, available_context_tokens)
                    logger.warning("Agentic RAG: Image section too large, truncating entire context")
            else:
                context = self._truncate_text_by_tokens(context, available_context_tokens)
            
            final_context_tokens = self.count_tokens(context)
            logger.info(f"Agentic RAG: Context truncated: {context_tokens:,} -> {final_context_tokens:,} tokens")
        
        sub_queries_text = "\n".join([f"- {sq}" for sq in sub_queries])
        
        # Detect if this is a summary query
        question_lower = question.lower()
        is_summary_query = any(kw in question_lower for kw in 
                              ['summary', 'summarize', 'overview', 'what is this document about',
                               'what does this document contain', 'what is in this document',
                               'tell me about', 'describe', 'explain this document'])
        
        if is_summary_query:
            system_prompt = """You are a document summarization assistant. Synthesize information from multiple sources to create a comprehensive summary.

CRITICAL RULES:
- Synthesize information from ALL provided context chunks
- Create a coherent summary even if chunks are from different sections
- Address all sub-questions to build a complete picture
- Include key points, main topics, and important information
- Organize information logically
- DO NOT say "context does not contain" - synthesize what IS available
- Focus on main themes and important details
- DO NOT add greetings, signatures, or closing statements"""
            
            user_prompt = f"""Original Question: {question}

Sub-Questions Analyzed:
{sub_queries_text}

Context from documents:
{context}

Instructions:
1. Analyze ALL retrieved context chunks
2. Synthesize information from multiple sources to create a comprehensive summary
3. Address all sub-questions to build a complete picture
4. Include: overview, key points, main topics, important information
5. Organize the summary logically
6. Use information from the context - synthesize what is available
7. DO NOT add greetings or closing statements

Summary:"""
        else:
            system_prompt = """You are a precise technical assistant that provides comprehensive, accurate answers by synthesizing information from multiple sources.

IMPORTANT: If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), you MUST USE THIS SECTION to answer questions about what is inside images.

CITATION RULES:
1. For EVERY claim or fact, include a citation using ONLY the source number: [Source 1], [Source 2], etc.
2. DO NOT include page numbers or filenames in the answer - these appear in the References section.
3. If information spans multiple sources, cite all: [Source 1, Source 2].
4. Place citations at the end of the sentence or paragraph they support.
5. WRONG: "[Source: filename (Page X)]" - CORRECT: "[Source 1]"
6. The user will see page numbers in the References section below your answer.

When asked:
- "what is in image X" or "what information is in image X"
- "what tools are in DRAWER X" or "what's in drawer X"
- "what part numbers are listed" or "what tools are listed"
- "give me information about images" or "what content is in the images"
- Any question mentioning images, drawers, tools, part numbers, or visual content

You MUST:
1. Look in the Image Content section FIRST (before checking other context)
2. Find the relevant image number or content
3. Provide detailed, specific information from the OCR text
4. Include exact part numbers, tool names, quantities, and other details from the OCR text
5. Do NOT say "context does not contain" if the Image Content section has relevant information

CRITICAL RULES:
- Synthesize information from ALL provided context chunks
- Work with the information that IS available in the context
- If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
- DO NOT say "context does not contain" unless you have thoroughly analyzed ALL chunks and found absolutely no relevant information
- Address all relevant sub-queries and synthesize their results
- Be specific and cite exact values, measurements, and specifications when available. ALWAYS CITE YOUR SOURCES.
- Include relevant details like dimensions, materials, standards, and procedures
- Maintain technical accuracy and precision
- DO NOT add greetings, signatures, or closing statements
- DO NOT repeat phrases or sentences
- DO NOT include "Best regards", "Thank you", or similar endings
- DO NOT make up information not in the context
- End your answer when you have provided the information - do not add unnecessary text

MULTILINGUAL INSTRUCTIONS:
- Detect the language of the user's question.
- ANSWER IN THE SAME LANGUAGE AS THE USER'S QUESTION.
- If the retrieved context is in a different language, TRANSLATE the relevant information into the language of the question.
- Do NOT answer in English if the user asks in Spanish, French, etc. (unless explicitly asked to)."""
            
            user_prompt = f"""Original Question: {question}

Sub-Questions Analyzed:
{sub_queries_text}

Context from documents:
{context}

Instructions:
1. Analyze ALL retrieved context chunks carefully
2. Synthesize information from multiple sources to answer the original question comprehensively
3. If the context contains relevant information, use it to provide a comprehensive answer
4. Address all sub-questions if they are relevant to the original question
5. Provide specific details, numbers, and specifications when available
6. Only say information is not available if you have thoroughly checked ALL chunks and found nothing relevant
7. DO NOT add greetings, signatures, or closing statements
8. DO NOT repeat information or phrases
9. Stop immediately after providing the answer

Answer:"""
        
        try:
            # Get temperature and max_tokens from UI config or defaults
            ui_temp = getattr(self, 'ui_config', {}).get('temperature', ARISConfig.DEFAULT_TEMPERATURE)
            ui_max_tokens = getattr(self, 'ui_config', {}).get('max_tokens', ARISConfig.DEFAULT_MAX_TOKENS)
            
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=ui_temp,  # Use UI config
                max_tokens=ui_max_tokens,  # Use UI config
                stop=["Best regards", "Thank you", "Please let me know", "If you have any other questions"]
            )
            
            if not response.choices or len(response.choices) == 0:
                raise ValueError("OpenAI API returned no choices in response")
            answer = response.choices[0].message.content
            if answer is None:
                raise ValueError("OpenAI API returned empty content in response")
            
            response_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            if response_tokens == 0:
                response_tokens = self.count_tokens(answer)
            
            answer = self._clean_answer(answer)
            return answer, response_tokens
        except Exception as e:
            logger.error(f"Error in OpenAI Agentic RAG synthesis: {e}", exc_info=True)
            # Fallback to standard generation
            return self._query_openai(question, context, relevant_docs)
    
    def _query_cerebras_agentic(
        self,
        question: str,
        sub_queries: List[str],
        context: str,
        relevant_docs: List = None,
        model: str = None
    ) -> tuple:
        """
        Query Cerebras with Agentic RAG synthesis prompt.
        
        Args:
            question: Original question
            sub_queries: List of sub-queries analyzed
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
        
        Returns:
            Tuple of (answer, response_tokens)
        """
        # For now, fallback to standard Cerebras query
        # TODO: Implement Cerebras-specific synthesis if needed
        logger.warning("Cerebras Agentic RAG synthesis not fully implemented, using standard query")
        return self._query_cerebras(question, context, relevant_docs, None, None)
    
