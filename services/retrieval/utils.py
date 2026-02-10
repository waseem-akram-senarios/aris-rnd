"""
Utility methods for text processing, token counting, and query analysis.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import os
import re
import logging
from typing import List, Dict, Optional

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class UtilsMixin:
    """Mixin providing utility methods for text processing, token counting, and query analysis capabilities."""
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        if not text:
            return 0
        try:
            import tiktoken
            # Use cl100k_base for OpenAI models (GPT-3.5/4)
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            logger.debug(f"count_tokens: {type(e).__name__}: {e}")
            # Fallback to rough estimate if tiktoken fails
            return len(text) // 4
    
    def _truncate_text_by_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit, preserving structure where possible.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens allowed
        
        Returns:
            Truncated text
        """
        if not text or max_tokens <= 0:
            return text
        
        current_tokens = self.count_tokens(text)
        if current_tokens <= max_tokens:
            return text
        
        # Estimate characters per token (rough: ~4 chars per token)
        chars_per_token = len(text) / max(current_tokens, 1)
        max_chars = int(max_tokens * chars_per_token * 0.9)  # 90% to be safe
        
        # Try to truncate at a natural boundary (sentence or chunk separator)
        if len(text) > max_chars:
            truncated = text[:max_chars]
            # Try to find a good break point
            last_separator = max(
                truncated.rfind('\n\n---\n\n'),  # Chunk separator
                truncated.rfind('\n\n'),  # Paragraph break
                truncated.rfind('. '),  # Sentence end
                truncated.rfind('\n')  # Line break
            )
            if last_separator > max_chars * 0.8:  # If we found a break point reasonably close
                truncated = text[:last_separator]
            
            # Verify token count
            while self.count_tokens(truncated) > max_tokens and len(truncated) > 100:
                truncated = truncated[:int(len(truncated) * 0.95)]  # Reduce by 5%
            
            return truncated
        
        return text
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
    def _detect_and_expand_query(self, question: str) -> tuple:
        """
        Detect if query is a summary/overview type and expand it.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple of (is_summary_query, expanded_query, suggested_k)
        """
        
        question_lower = question.lower().strip()
        
        # Keywords that indicate summary/overview queries
        summary_keywords = [
            'summary', 'summarize', 'overview', 'what is this document about',
            'what does this document contain', 'what is in this document',
            'tell me about', 'describe', 'explain this document',
            'what are the main points', 'key points', 'highlights',
            'what is the document about', 'document summary'
        ]
        
        is_summary = any(keyword in question_lower for keyword in summary_keywords)
        
        if is_summary:
            # Expand query to include multiple aspects
            expanded = f"{question} Include: overview, introduction, key points, main topics, important information, highlights, main themes, primary content"
            # Increase k for summaries (more chunks = better coverage)
            summary_config = ARISConfig.get_summary_query_config()
            suggested_k = max(
                int(ARISConfig.DEFAULT_RETRIEVAL_K * summary_config['k_multiplier']),
                summary_config['min_k']
            )
            return True, expanded, suggested_k
        
        return False, question, None
    def _get_recent_documents(self, max_age_hours: int = 24) -> List[str]:
        """
        Get list of recently uploaded documents.
        
        Args:
            max_age_hours: Maximum age in hours for a document to be considered "recent"
        
        Returns:
            List of document names that were uploaded recently
        """
        try:
            import json
            from datetime import datetime, timedelta

            registry_path = getattr(ARISConfig, 'DOCUMENT_REGISTRY_PATH', None)
            if registry_path and os.path.exists(registry_path):
                with open(registry_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)

                docs = list(raw.values()) if isinstance(raw, dict) else (raw or [])
                cutoff = datetime.now() - timedelta(hours=max_age_hours)

                recent: List[tuple] = []
                for d in docs:
                    if not isinstance(d, dict):
                        continue
                    name = d.get('document_name') or d.get('original_document_name')
                    ts = d.get('updated_at') or d.get('created_at')
                    if not name or not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(ts)
                    except Exception as e:
                        logger.warning(f"operation: {type(e).__name__}: {e}")
                        continue
                    if dt >= cutoff:
                        recent.append((dt, name))

                recent.sort(key=lambda x: x[0], reverse=True)
                return [name for _, name in recent]

        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass

        # Fallback: if no registry timestamps, use known indexed documents (best-effort)
        if hasattr(self, 'document_index_map') and self.document_index_map:
            return list(self.document_index_map.keys())
        return []
    def _extract_document_number(self, filename: str) -> Optional[int]:
        """
        Extract document number from filename like 'file (1).pdf' -> 1
        
        Args:
            filename: Document filename (with or without path)
        
        Returns:
            Document number if found, None otherwise
        """
        import re
        # Extract just the filename if path is included
        basename = os.path.basename(filename) if filename else ""
        # Look for pattern like "(1)", "(2)", etc.
        match = re.search(r'\((\d+)\)', basename)
        return int(match.group(1)) if match else None
    def _detect_document_in_question(self, question: str, available_docs: List[str]) -> Optional[List[str]]:
        """
        Detect if the question mentions a specific document name.
        
        This helps automatically filter to the correct document when user asks
        "What is in VUORMAR MK?" or "Tell me about EM11 document".
        
        Args:
            question: The user's question
            available_docs: List of available document names
            
        Returns:
            List of detected document names, or None if no specific document mentioned
        """
        import re
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if not question or not available_docs:
            return None
        
        question_lower = question.lower()
        detected = []
        
        # Sort documents by name length (descending) to match longer names first
        # This ensures "VUORMAR MK" matches before "VUORMAR"
        sorted_docs = sorted(available_docs, key=lambda x: len(x), reverse=True)
        
        for doc_name in sorted_docs:
            # Get base name without extension
            base_name = os.path.splitext(doc_name)[0].lower()
            doc_name_lower = doc_name.lower()
            
            # Check various patterns:
            # 1. Exact match (case-insensitive): "vuormar mk"
            # 2. Without extension: "vuormar mk.pdf" -> "vuormar mk"
            # 3. With "document" suffix: "vuormar mk document"
            # 4. Separated words: "vuormar" and "mk" both in question
            
            # Pattern 1: Direct name match (most specific)
            if base_name in question_lower or doc_name_lower.replace('.pdf', '') in question_lower:
                # Make sure it's not a partial match of a longer document
                # E.g., don't match "VUORMAR" when "VUORMAR MK" is also available
                already_matched = any(
                    base_name in os.path.splitext(d)[0].lower() and len(d) > len(doc_name)
                    for d in detected
                )
                if not already_matched:
                    detected.append(doc_name)
                    logger.info(f"Detected document mention: '{doc_name}' (direct match)")
                    continue
            
            # Pattern 2: Check if all significant words from doc name are in question
            # Split doc name into words (remove common suffixes like MK, v1, etc.)
            doc_words = re.split(r'[\s_\-\.]+', base_name)
            doc_words = [w for w in doc_words if len(w) > 1]  # Filter out single chars
            
            if len(doc_words) >= 2:
                # Multi-word document name - all words must be present
                words_found = sum(1 for w in doc_words if w in question_lower)
                if words_found == len(doc_words):
                    # All words found - likely this document
                    already_in_detected = doc_name in detected
                    if not already_in_detected:
                        detected.append(doc_name)
                        logger.info(f"Detected document mention: '{doc_name}' (all words match: {doc_words})")
        
        # If we found multiple documents, prefer the most specific one (longest name with most matches)
        if len(detected) > 1:
            # Keep only the most specific (longest) document names
            # E.g., if both "VUORMAR.pdf" and "VUORMAR MK.pdf" detected, keep only "VUORMAR MK.pdf"
            # unless the question specifically mentions both
            filtered_detected = []
            for doc in detected:
                base = os.path.splitext(doc)[0].lower()
                # Check if this doc is a subset of another detected doc
                is_subset = any(
                    base in os.path.splitext(other)[0].lower() and len(other) > len(doc)
                    for other in detected
                )
                if not is_subset:
                    filtered_detected.append(doc)
            
            if filtered_detected:
                detected = filtered_detected
                logger.info(f"Filtered to most specific documents: {detected}")
        
        return detected if detected else None
    def _detect_occurrence_query(self, question: str) -> tuple:
        """Detect if a question is asking to find all occurrences of a term.

        Returns:
            (is_occurrence_query, term)
        """
        if not question:
            return False, ""

        q = question.strip()
        ql = q.lower()

        # FIXED: Very restrictive triggers - only for explicit "find all occurrences" type queries
        # NOT for general questions like "Where is the email?"
        import re
        
        # Exclude patterns that are regular questions (not occurrence queries)
        # These should be handled by normal RAG retrieval
        exclusions = [
            "what is",
            "what are",
            "how does",
            "how do",
            "explain",
            "describe",
            "tell me about",
            "information about",
            "details about",
            "schematic",
            "diagram",
            "image",
            "picture",
            "figure",
            "contact",
            "email",
            "phone",
            "address",
            "number",
            "in the document",
            "in document",
            "document me",  # For Roman English like "document me se"
            "btaein",  # Roman English
            "batao",   # Roman English
            "kya hai", # Roman English
        ]
        
        # If question contains exclusion patterns, it's not an occurrence query
        if any(e in ql for e in exclusions):
            return False, ""
        
        # Only trigger for very explicit occurrence search patterns
        # Pattern 1: Quoted term search - find "exact phrase"
        m = re.search(r'"([^"]+)"', q)
        if m and m.group(1).strip():
            # Check if this is a "find all occurrences of X" type query
            if any(t in ql for t in ["occurrence", "find all", "show me all", "highlight"]):
                return True, m.group(1).strip()
        
        # Pattern 2: Explicit "occurrences of X" 
        m = re.search(r"(?:all\s+)?occurrences?\s+of\s+(.+)$", ql)
        if m and m.group(1).strip():
            return True, q[m.start(1):m.end(1)].strip()
        
        # Pattern 3: "where does X appear/occur/show up" (very specific)
        m = re.search(r"where\s+(?:does|do)\s+(.+?)\s+(?:appear|occur|show\s+up)\b", ql)
        if m and m.group(1).strip():
            return True, q[m.start(1):m.end(1)].strip()
        
        # Pattern 4: "find all X" or "show me all X" (explicit all)
        m = re.search(r"(?:find|show\s+me)\s+all\s+(.+)$", ql)
        if m and m.group(1).strip():
            return True, q[m.start(1):m.end(1)].strip()
        
        # Default: NOT an occurrence query - let normal RAG handle it
        return False, ""
    def _build_occurrence_answer(self, term: str, source: str, occurrences: List[Dict], truncated: bool) -> str:
        """Build a human-readable answer string for occurrence results."""
        safe_term = term.strip()
        total = len(occurrences)
        header = f"Found {total} occurrence(s) of '{safe_term}' in {source}."
        if truncated:
            header += " (Results truncated.)"

        lines = [header, ""]
        for occ in occurrences:
            page = occ.get('page')
            image_idx = occ.get('image_index')
            snippet = (occ.get('snippet') or "").strip()
            loc_parts = []
            if page:
                loc_parts.append(f"Page {page}")
            if image_idx is not None:
                loc_parts.append(f"Image {image_idx}")
            loc = " | ".join(loc_parts) if loc_parts else "Text"
            if snippet:
                lines.append(f"- {loc}: {snippet}")
            else:
                lines.append(f"- {loc}")
        return "\n".join(lines)

