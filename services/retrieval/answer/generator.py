"""
LLM answer generation using OpenAI and Cerebras APIs.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import os
import logging
import requests
from typing import List, Dict, Optional

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class AnswerGeneratorMixin:
    """Mixin providing llm answer generation using openai and cerebras apis capabilities."""
    
    def _query_offline(self, question: str, context: str, relevant_docs: List = None) -> tuple:
        parts = []
        if relevant_docs:
            for doc in relevant_docs[:3]:
                try:
                    source = doc.metadata.get('source', 'Unknown') if hasattr(doc, 'metadata') and doc.metadata else 'Unknown'
                    page = doc.metadata.get('page', None) if hasattr(doc, 'metadata') and doc.metadata else None
                    # Ensure page is always set (fallback to 1)
                    if page is None:
                        page = 1
                    snippet = (doc.page_content or '').strip().replace('\n', ' ')
                    if len(snippet) > 350:
                        snippet = snippet[:350] + "..."
                    # Page is always set now, so always include it
                    parts.append(f"- ({source}, page {page}) {snippet}")
                except Exception as e:
                    logger.debug(f"_query_offline: {type(e).__name__}: {e}")
                    continue
        if not parts:
            preview = (context or '').strip().replace('\n', ' ')
            if len(preview) > 800:
                preview = preview[:800] + "..."
            if preview:
                parts = [preview]
        answer = "OpenAI is not configured (missing OPENAI_API_KEY). Retrieved context:\n" + "\n".join(parts)
        return answer, self.count_tokens(answer)
    
    def _query_openai(self, question: str, context: str, relevant_docs: List = None, mentioned_documents: List = None, question_doc_number: int = None, response_language: str = None, model: str = None) -> tuple:
        """
        Query OpenAI with maximum accuracy settings.
        
        Args:
            question: The question to answer
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
            mentioned_documents: List of documents mentioned in the question (for filtering)
            question_doc_number: Document number extracted from question (e.g., 1, 2)
            response_language: Language to answer in
            model: Specific model to use (defaults to self.openai_model)
        """
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Select model: use provided model, then instance model, then default
        target_model = model or self.openai_model or ARISConfig.OPENAI_MODEL
        
        # Truncate context if it exceeds model's token limit
        # Most OpenAI models have 128k context limit, reserve space for prompt and response
        MAX_CONTEXT_TOKENS = 100000  # Reserve ~28k for prompt, question, and response
        context_tokens = self.count_tokens(context)
        
        if context_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(
                f"Context too large ({context_tokens:,} tokens > {MAX_CONTEXT_TOKENS:,} limit). "
                f"Truncating to fit within model limits..."
            )
            
            # Intelligent truncation: try to preserve important sections
            # 1. Check if there's an image content section - preserve it if present
            image_section_start = context.find('IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)')
            image_section_end = context.find('\n\n---\n\n', image_section_start + 100) if image_section_start >= 0 else -1
            
            # 2. Calculate how much we need to truncate
            question_tokens = self.count_tokens(question)
            system_prompt_estimate = 500  # Rough estimate for system prompt
            buffer_tokens = 2000  # Safety buffer
            available_context_tokens = MAX_CONTEXT_TOKENS - question_tokens - system_prompt_estimate - buffer_tokens
            
            # 3. If image section exists, preserve it and truncate from the end
            if image_section_start >= 0 and image_section_end >= 0:
                image_section = context[image_section_start:image_section_end]
                image_section_tokens = self.count_tokens(image_section)
                remaining_tokens = available_context_tokens - image_section_tokens
                
                if remaining_tokens > 0:
                    # Keep image section + truncate main context
                    main_context = context[:image_section_start]
                    # Truncate main context to fit
                    truncated_main = self._truncate_text_by_tokens(main_context, remaining_tokens)
                    context = truncated_main + "\n\n" + image_section
                    logger.info(f"Preserved image section ({image_section_tokens:,} tokens), truncated main context to {remaining_tokens:,} tokens")
                else:
                    # Image section itself is too large, truncate everything
                    context = self._truncate_text_by_tokens(context, available_context_tokens)
                    logger.warning("Image section too large, truncating entire context")
            else:
                # No image section, truncate from the end
                context = self._truncate_text_by_tokens(context, available_context_tokens)
            
            final_context_tokens = self.count_tokens(context)
            logger.info(f"Context truncated: {context_tokens:,} -> {final_context_tokens:,} tokens")
        
        # #region agent log
        try:
            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                import json
                context_has_image_section = 'IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)' in context
                image_section_start = context.find('IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)') if context_has_image_section else -1
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rag_system.py:2819","message":"_query_openai called","data":{"context_length":len(context),"context_has_image_section":context_has_image_section,"image_section_start":image_section_start,"question":question[:100]},"timestamp":int(time_module.time()*1000)})+"\n")
        except Exception as e:
            logger.warning(f"operation: {type(e).__name__}: {e}")
            pass
        # #endregion
        
        # Detect if this is a summary query
        question_lower = question.lower()
        is_summary_query = any(kw in question_lower for kw in 
                              ['summary', 'summarize', 'overview', 'what is this document about',
                               'what does this document contain', 'what is in this document',
                               'tell me about', 'describe', 'explain this document'])
        
        # Build language instruction
        language_instruction = ""
        if response_language:
            language_instruction = f"\n\nCRITICAL: You MUST answer strictly in {response_language}. Translate any information from the context into {response_language} if necessary. Do not answer in any other language."
        else:
            language_instruction = """
                MULTILINGUAL INSTRUCTIONS:
                - Detect the language of the user's question.
                - ANSWER IN THE SAME LANGUAGE AS THE USER'S QUESTION.
                - If the retrieved context is in a different language, TRANSLATE the relevant information into the language of the question.
                - Do NOT answer in English if the user asks in Spanish, French, etc. (unless explicitly asked to).

                ROMAN ENGLISH / TRANSLITERATED TEXT HANDLING:
                - If the question is in Roman English (e.g., "ye kya hai", "mujhe batao", "kaise kare") or other transliterated languages:
                - Recognize this as a valid question in that language (e.g., Hindi/Urdu written in Latin script)
                - Provide a DETAILED and COMPREHENSIVE answer, not a brief one
                - Answer in the SAME format as the question (Roman English if asked in Roman English)
                - Include all relevant details, specifications, and information from the context
                - Do NOT provide shorter answers just because the question is in Roman/transliterated text
                - Treat Roman English questions with the SAME importance and detail level as English questions"""

        if is_summary_query:
            # Use synthesis-friendly prompt for summaries
            system_prompt = f"""You are a document summarization assistant. Your task is to synthesize information from the provided context to create a comprehensive summary.{language_instruction}

                CRITICAL RULES:
                - Synthesize information from ALL provided context chunks to create a coherent summary
                - Create a summary even if chunks are from different sections of the document
                - Include key points, main topics, and important information from the context
                - Organize information logically (overview, main points, important details)
                - Focus on main themes, important details, and key information
                - DO NOT add greetings, signatures, or closing statements
                - End your answer when you have provided the summary"""
            
            user_prompt = f"""Context from documents:
                {context}

                Question: {question}

                Instructions:
                1. Read ALL context chunks carefully
                2. Synthesize information from multiple chunks to create a comprehensive summary
                3. Include: overview, key points, main topics, important information
                4. Organize the summary logically
                5. Use information from the context - do not say it's not available
                6. DO NOT add greetings or closing statements
                7. If the context does not contain relevant information, simply say "The context does not contain information relevant to summarizing the document." and end the answer immediately.
                8. Do NOT add citations if context does not contain specific information - just summarize what is there without citing.

                Summary:"""
        else:
            # Synthesis-friendly prompt for all queries - encourages working with available information
            # Add document filtering instruction if specific document mentioned
            document_filter_instruction = ""
            if mentioned_documents and question_doc_number is not None:
                mentioned_doc_name = os.path.basename(mentioned_documents[0]) if mentioned_documents else ""
                document_filter_instruction = f"""
                    CRITICAL DOCUMENT FILTERING: The question specifically asks about "{mentioned_doc_name}". 
                    - You MUST ONLY use information from this specific document
                    - DO NOT use information from other documents, even if they have similar names
                    - If the context contains information from other documents, IGNORE it
                    - Only answer based on the specified document: {mentioned_doc_name}
                    - If the specified document is not in the context, state that clearly"""
            
            system_prompt = f"""You are a precise technical assistant that provides accurate, detailed answers by synthesizing information from the provided context.{language_instruction}

                IMPORTANT: If the context includes a "Document Metadata" section, use it to answer questions about document properties like image counts, page counts, etc. When asked about images in a document, check the Document Metadata section first. If the metadata shows "exact count not available" but images are detected, state that images are present but the exact count requires re-processing the document.{document_filter_instruction}
                CRITICAL: If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), you MUST USE THIS SECTION to answer questions about what is inside images. This section contains OCR text extracted from images and is the PRIMARY and MOST RELIABLE source for answering questions about image content.

                CITATION RULES:
                1. For EVERY claim or fact, include a citation using ONLY the source number: [Source 1], [Source 2], etc.
                2. DO NOT include page numbers or filenames in the answer text - these appear in the References section.
                3. If information spans multiple sources, cite all: [Source 1, Source 2].
                4. Place citations at the end of the sentence or paragraph they support.
                5. WRONG: "[Source: Policy Manual (Page 6)]" - CORRECT: "[Source 1]"
                6. The user will see page numbers in the References section below your answer.

                When asked:
                - "what is in image X" or "what information is in image X"
                - "what tools are in DRAWER X" or "what's in drawer X"
                - "what part numbers are listed" or "what tools are listed"
                - "give me information about images" or "what content is in the images"
                - "where can I find [tool name]" or "where is [item]"
                - "what drawer has [item]" or "location of [part number]"
                - Any question mentioning images, drawers, tools, part numbers, or visual content

                You MUST:
                1. Look in the Image Content section FIRST (before checking other context)
                2. Find the relevant image number or content
                3. Search the OCR text for the specific tool/item name or part number mentioned in the question
                4. Provide detailed, specific information from the OCR text
                5. Include exact part numbers, tool names, quantities, drawer numbers, and other details from the OCR text
                6. Do NOT say "context does not contain" if the Image Content section has relevant information

                IMPORTANT: When asked about specific tools, items, or part numbers (e.g., "Where can I find the Mallet?"):
                1. FIRST check the "=== IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES) ===" section
                2. Search the OCR text for the tool/item name or part number
                3. Look for drawer numbers, locations, or quantities associated with the item
                4. Provide specific information from the OCR text, including drawer numbers, page numbers, and quantities
                5. DO NOT say "context does not contain" if you haven't thoroughly searched the Image Content section

                CRITICAL RULES:
                - Synthesize information from ALL provided context chunks to answer the question
                - Work with the information that IS available in the context
                - DO NOT say "context does not contain" unless you have thoroughly analyzed ALL chunks and found absolutely no relevant information
                - Be specific and cite exact values, measurements, and specifications when available.
                - Include relevant details like dimensions, materials, standards, and procedures
                - Maintain technical accuracy and precision
                - If multiple sources provide information, synthesize them clearly
                - DO NOT add greetings, signatures, or closing statements
                - DO NOT repeat phrases or sentences
                - DO NOT include "Best regards", "Thank you", or similar endings
                - DO NOT make up information not in the context
                - DO NOT add citations if the information is not directly supported by the context.
                - DO NOT add citations if context does not contain specific information - just answer with the information that is there without citing.
                - End your answer when you have provided the information - do not add unnecessary text"""
        
            # Add document filtering instruction to user prompt if specific document mentioned
            user_doc_filter_instruction = ""
            if mentioned_documents and question_doc_number is not None:
                mentioned_doc_name = os.path.basename(mentioned_documents[0]) if mentioned_documents else ""
                user_doc_filter_instruction = f"\n\nCRITICAL: The question asks specifically about \"{mentioned_doc_name}\". Only use information from this document. Ignore information from other documents."
            
            user_prompt = f"""Context from documents:
                {context}

                Question: {question}{user_doc_filter_instruction}

                Instructions:
                1. If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), check it FIRST for questions about images, drawers, tools, or part numbers
                2. For questions about specific tools, items, or part numbers (e.g., "Where can I find the Mallet?"), search the Image Content section OCR text for the tool/item name or part number
                3. Read ALL context chunks carefully
                4. Synthesize information from the context to answer the question
                5. If the context contains relevant information, use it to provide a comprehensive answer
                6. Include specific details, numbers, and specifications when available
                7. For image-related questions, prioritize information from the Image Content section
                8. When searching for tools/items, look for drawer numbers, locations, quantities, and part numbers in the OCR text
                9. Only say information is not available if you have thoroughly checked ALL chunks AND the Image Content section (if present) and found nothing relevant
                10. DO NOT add greetings, signatures, or closing statements
                11. DO NOT repeat information or phrases
                12. DO NOT add citations if the information is not directly supported by the context.
                13. DO NOT add citations if context does not contain specific information - just answer with the information that is there without citing.
                14. Stop immediately after providing the answer

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
                stop=["Best regards", "Thank you", "Please let me know", "If you have any other questions"]  # Stop at common endings
            )
            # Check if response has choices
            if not response.choices or len(response.choices) == 0:
                raise ValueError("OpenAI API returned no choices in response")
            answer = response.choices[0].message.content
            if answer is None:
                raise ValueError("OpenAI API returned empty content in response")
            
            # #region agent log
            try:
                with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                    import json
                    # Check if answer mentions image content keywords
                    has_image_keywords = any(kw in answer.lower() for kw in ['image', 'drawer', 'tool', 'part number', 'ocr', '65300'])
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rag_system.py:2943","message":"LLM response received","data":{"answer_length":len(answer),"has_image_keywords":has_image_keywords,"answer_preview":answer[:300]},"timestamp":int(time_module.time()*1000)})+"\n")
            except Exception as e:
                logger.warning(f"operation: {type(e).__name__}: {e}")
                pass
            # #endregion
            
            # Get token usage from response
            response_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            if response_tokens == 0:
                # Fallback: estimate tokens in answer
                response_tokens = self.count_tokens(answer)
            
            # Clean up any repetitive or unwanted endings
            answer = self._clean_answer(answer)
            
            # #region agent log
            try:
                with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                    import json
                    has_image_keywords_after = any(kw in answer.lower() for kw in ['image', 'drawer', 'tool', 'part number', 'ocr', '65300'])
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rag_system.py:2955","message":"LLM response after cleaning","data":{"answer_length":len(answer),"has_image_keywords":has_image_keywords_after,"answer_preview":answer[:300]},"timestamp":int(time_module.time()*1000)})+"\n")
            except Exception as e:
                logger.warning(f"operation: {type(e).__name__}: {e}")
                pass
            # #endregion
            
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
    
    def _query_cerebras(self, question: str, context: str, relevant_docs: List = None, mentioned_documents: List = None, question_doc_number: int = None, response_language: str = None, model: str = None) -> tuple:
        """Query Cerebras API with maximum accuracy settings
        
        Args:
            question: The question to answer
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
            mentioned_documents: List of documents mentioned in the question (for filtering)
            question_doc_number: Document number extracted from question (e.g., 1, 2)
            response_language: Language to answer in
            model: Specific model to use (defaults to self.cerebras_model)
        """
        
        # Build language instruction
        language_instruction = ""
        if response_language:
            language_instruction = f"\n\nCRITICAL: You MUST answer strictly in {response_language}. Translate any information from the context into {response_language} if necessary. Do not answer in any other language."
        else:
             language_instruction = """
                MULTILINGUAL INSTRUCTIONS:
                - Detect the language of the user's question.
                - ANSWER IN THE SAME LANGUAGE AS THE USER'S QUESTION.
                - If the retrieved context is in a different language, TRANSLATE the relevant information into the language of the question.
                - Do NOT answer in English if the user asks in Spanish, French, etc. (unless explicitly asked to)."""

        # Synthesis-friendly prompt for Cerebras
        prompt = f"""You are a precise technical assistant. Synthesize information from the provided context to answer the question. Be specific and accurate.{language_instruction}

            CITATION RULES:
            1. For EVERY claim or fact, include a citation using ONLY the source number: [Source 1], [Source 2], etc.
            2. DO NOT include page numbers or filenames in the answer - these appear in the References section.
            3. If information spans multiple sources, cite all: [Source 1, Source 2].
            4. Place citations at the end of the sentence or paragraph they support.
            5. WRONG: "[Source: filename (Page X)]" - CORRECT: "[Source 1]"

            CRITICAL: DO NOT add greetings, signatures, or closing statements. DO NOT repeat phrases. End your answer when you have provided the information.

            Context:
            {context}

            Question: {question}

            Instructions:
            - Synthesize information from ALL context chunks to answer the question
            - Work with the information that IS available in the context
            - If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
            - Only say information is not available if you have thoroughly checked ALL chunks and found nothing relevant
            - Be specific with numbers, measurements, and technical details. ALWAYS CITE YOUR SOURCES.
            - Provide comprehensive and accurate answers
            - DO NOT add "Best regards", "Thank you", or similar endings
            - DO NOT add citations if the information is not directly supported by the context.
            - DO NOT add citations if context does not contain specific information - just answer with the information that is there without citing.
            - Stop immediately after providing the answer

            Answer:"""
        
        headers = {
            "Authorization": f"Bearer {self.cerebras_api_key}",
            "Content-Type": "application/json"
        }
        
        # Use selected Cerebras model
        try:
            # Get temperature and max_tokens from UI config or defaults
            ui_temp = getattr(self, 'ui_config', {}).get('temperature', ARISConfig.DEFAULT_TEMPERATURE)
            ui_max_tokens = getattr(self, 'ui_config', {}).get('max_tokens', ARISConfig.DEFAULT_MAX_TOKENS)
            
            data = {
                "model": self.cerebras_model,
                "prompt": prompt,
                "max_tokens": ui_max_tokens,  # Use UI config
                "temperature": ui_temp  # Use UI config
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
            logger.debug(f"operation: {type(e).__name__}: {e}")
            error_msg = f"Error: Could not get response from Cerebras API: {str(e)}"
            return error_msg, self.count_tokens(error_msg)
    
