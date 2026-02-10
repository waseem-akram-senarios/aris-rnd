"""
Snippet generation, semantic similarity, and keyword extraction for citations.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class SnippetMixin:
    """Mixin providing snippet generation, semantic similarity, and keyword extraction for citations capabilities."""
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts using embeddings.
        Generic, dynamic approach that works for any document type.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score between 0 and 1
        """
        try:
            # Use embeddings to calculate semantic similarity
            if hasattr(self, 'embeddings') and self.embeddings:
                # Get embeddings for both texts
                emb1 = self.embeddings.embed_query(text1[:1000])  # Limit length for efficiency
                emb2 = self.embeddings.embed_query(text2[:1000])
                
                # Calculate cosine similarity
                import numpy as np
                dot_product = np.dot(emb1, emb2)
                norm1 = np.linalg.norm(emb1)
                norm2 = np.linalg.norm(emb2)
                
                if norm1 > 0 and norm2 > 0:
                    similarity = dot_product / (norm1 * norm2)
                    return float(similarity)
        except Exception as e:
            logger.debug(f"_calculate_semantic_similarity: {type(e).__name__}: {e}")
            pass
        
        # Fallback to word overlap similarity if embeddings fail
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0
    
    def _generate_context_snippet(self, chunk_text: str, query: str, max_length: int = 500, 
                                    query_language: str = None, doc_metadata: dict = None) -> str:
        """
        Generate snippet centered around query-relevant content using dynamic semantic matching.
        Generic solution that works for all document types without hardcoded mappings.
        
        ENHANCED: Now supports language-aware snippet selection to prefer English text
        when the query is in English (fixes cross-language citation mismatch issue).
        
        Args:
            chunk_text: Full chunk text content
            query: User query to find relevant portions
            max_length: Maximum snippet length in characters
            query_language: Language of the query ('en', 'es', etc.) for language-aware snippets
            doc_metadata: Document metadata containing 'text_english' for translated content
        
        Returns:
            Cleaned snippet with query-relevant content in the appropriate language
        """
        import re
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # ENHANCEMENT: For English queries on non-English documents, prefer English text if available
        # This fixes the QA issue where Spanish source text was shown for English queries
        if query_language and query_language.lower() in ('en', 'english'):
            # Try to get English translation from metadata
            if doc_metadata and doc_metadata.get('text_english'):
                english_text = doc_metadata.get('text_english', '')
                if english_text and len(english_text) > 50:
                    # Use English translation for the snippet if query is in English
                    logger.debug(f"Using English translation for snippet (query_language={query_language})")
                    chunk_text = english_text
        
        # Clean chunk text - remove page markers
        cleaned_text = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', chunk_text).strip()
        if not cleaned_text:
            cleaned_text = chunk_text
        
        # If chunk is shorter than max_length, return it all
        if len(cleaned_text) <= max_length:
            return cleaned_text
        
        # Strategy 1: Try semantic similarity-based sentence extraction (most generic)
        try:
            semantic_snippet = self._extract_semantic_snippet(cleaned_text, query, max_length)
            if semantic_snippet and len(semantic_snippet) > 50:  # Only use if meaningful
                return semantic_snippet
        except Exception as e:
            logger.debug(f"Semantic snippet extraction failed: {e}")
        
        # Strategy 2: Fallback to keyword-based matching with dynamic word extraction
        query_words = re.findall(r'\b\w+\b', query.lower())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'about', 'tell', 'me', 'what', 'when', 'where', 'who', 'why', 'how'}
        query_keywords = [w for w in query_words if w not in stop_words and len(w) > 2]
        
        # If no meaningful keywords, use sentence-level semantic extraction
        if not query_keywords:
            return self._extract_sentences_snippet(cleaned_text, max_length, query=query)
        
        # Find positions of query keywords in text (with fuzzy matching)
        keyword_positions = []
        text_lower = cleaned_text.lower()
        
        for keyword in query_keywords:
            # Exact matches
            start = 0
            while True:
                pos = text_lower.find(keyword, start)
                if pos == -1:
                    break
                keyword_positions.append(pos)
                start = pos + 1
            
            # Partial word matches for longer keywords (dynamic, not hardcoded)
            if len(keyword) > 4:
                # Try stem-like matching (first 4-5 chars)
                stem_length = min(5, len(keyword) - 1)
                stem = keyword[:stem_length]
                start = 0
                while True:
                    pos = text_lower.find(stem, start)
                    if pos == -1:
                        break
                    # Check word boundaries
                    if (pos == 0 or not text_lower[pos-1].isalnum()) and \
                       (pos + len(stem) >= len(text_lower) or not text_lower[pos + len(stem)].isalnum()):
                        keyword_positions.append(pos)
                    start = pos + 1
        
        if not keyword_positions:
            # No keyword matches found, use semantic sentence extraction
            return self._extract_sentences_snippet(cleaned_text, max_length, query_keywords, query=query)
        
        # Find the center of keyword positions
        keyword_positions.sort()
        center_pos = keyword_positions[len(keyword_positions) // 2]
        
        # Extract context around center position
        start_pos = max(0, center_pos - max_length // 2)
        end_pos = min(len(cleaned_text), start_pos + max_length)
        
        # Adjust to preserve sentence boundaries
        if start_pos > 0:
            search_start = max(0, start_pos - 100)
            period = cleaned_text.rfind('.', search_start, start_pos)
            exclamation = cleaned_text.rfind('!', search_start, start_pos)
            question = cleaned_text.rfind('?', search_start, start_pos)
            sentence_end = max(period, exclamation, question)
            if sentence_end > start_pos - 50:
                start_pos = sentence_end + 1
                while start_pos < len(cleaned_text) and cleaned_text[start_pos].isspace():
                    start_pos += 1
        
        if end_pos < len(cleaned_text):
            period = cleaned_text.find('.', end_pos - 50, end_pos + 50)
            exclamation = cleaned_text.find('!', end_pos - 50, end_pos + 50)
            question = cleaned_text.find('?', end_pos - 50, end_pos + 50)
            sentence_end = min([p for p in [period, exclamation, question] if p != -1], default=-1)
            if sentence_end != -1 and sentence_end > end_pos - 50:
                end_pos = sentence_end + 1
        
        snippet = cleaned_text[start_pos:end_pos].strip()
        
        if start_pos > 0:
            snippet = "..." + snippet
        if end_pos < len(cleaned_text):
            snippet = snippet + "..."
        
        return snippet
    
    def _extract_semantic_snippet(self, text: str, query: str, max_length: int) -> str:
        """
        Extract snippet using semantic similarity - enhanced approach for better accuracy.
        
        Args:
            text: Full text to extract from
            query: Query to match against
            max_length: Maximum snippet length
        
        Returns:
            Most semantically relevant snippet
        """
        import re
        
        # Split into sentences with better pattern matching
        # Enhanced: Handle abbreviations, decimals, and other edge cases
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=\d)\.\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        
        if not sentences:
            return text[:max_length] + ("..." if len(text) > max_length else "")
        
        # Score each sentence by semantic similarity to query (enhanced)
        scored_sentences = []
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        for sentence in sentences:
            if len(sentence) < 10:  # Skip very short sentences
                continue
            
            # Calculate semantic similarity
            similarity = self._calculate_semantic_similarity(sentence, query)
            
            # Boost score if query keywords appear in sentence (hybrid approach)
            sentence_lower = sentence.lower()
            sentence_words = set(re.findall(r'\b\w+\b', sentence_lower))
            keyword_overlap = len(query_words.intersection(sentence_words))
            keyword_boost = min(0.2, keyword_overlap * 0.05)  # Max 0.2 boost
            
            # Combined score: semantic similarity + keyword boost
            combined_score = min(1.0, similarity + keyword_boost)
            
            scored_sentences.append((combined_score, similarity, sentence))
        
        if not scored_sentences:
            return text[:max_length] + ("..." if len(text) > max_length else "")
        
        # Sort by combined score (highest first), then by semantic similarity
        scored_sentences.sort(key=lambda x: (x[0], x[1]), reverse=True)
        
        # Select top sentences up to max_length (using combined score)
        selected = []
        total_length = 0
        for combined_score, semantic_score, sentence in scored_sentences:
            if total_length + len(sentence) + 1 <= max_length:
                selected.append(sentence)
                total_length += len(sentence) + 1
            else:
                # Try to fit partial sentence if close to max_length
                remaining = max_length - total_length - 3  # Reserve for "..."
                if remaining > 50 and len(sentence) > remaining:
                    # Try to break at sentence boundary
                    partial = sentence[:remaining].rsplit('.', 1)[0]
                    if partial and len(partial) > 30:
                        selected.append(partial + "...")
                break
        
        if selected:
            snippet = " ".join(selected)
            if total_length < len(text):
                snippet += "..."
            return snippet
        
        # Fallback: return highest scoring sentence
        if scored_sentences:
            return scored_sentences[0][2][:max_length] + ("..." if len(scored_sentences[0][2]) > max_length else "")
        
        # Last resort: return beginning of text
        return text[:max_length] + ("..." if len(text) > max_length else "")
    
    def _extract_sentences_snippet(self, text: str, max_length: int, keywords: Optional[List[str]] = None, query: Optional[str] = None) -> str:
        """
        Extract snippet by scoring sentences dynamically - generic approach for any document.
        Uses semantic similarity when available, falls back to keyword matching.
        
        Args:
            text: Full text to extract from
            max_length: Maximum snippet length
            keywords: Optional keywords to score sentences against
            query: Optional query for semantic matching
        
        Returns:
            Snippet composed of most relevant sentences
        """
        import re
        
        # Split into sentences
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            snippet = text[:max_length]
            if len(text) > max_length:
                snippet += "..."
            return snippet
        
        scored_sentences = []
        
        # Strategy 1: Use semantic similarity if query provided and embeddings available
        if query and hasattr(self, 'embeddings') and self.embeddings:
            try:
                for sentence in sentences:
                    if len(sentence) < 10:  # Skip very short sentences
                        continue
                    similarity = self._calculate_semantic_similarity(sentence, query)
                    scored_sentences.append((similarity, sentence, 'semantic'))
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                pass  # Fall back to keyword matching
        
        # Strategy 2: Keyword-based scoring (dynamic, no hardcoded patterns)
        if not scored_sentences and keywords:
            text_lower = text.lower()
            for sentence in sentences:
                if len(sentence) < 10:
                    continue
                score = 0
                sentence_lower = sentence.lower()
                
                # Count keyword matches (exact and partial)
                for keyword in keywords:
                    if keyword in sentence_lower:
                        score += 1.0
                    # Dynamic partial matching for longer keywords
                    elif len(keyword) > 4:
                        stem = keyword[:min(5, len(keyword)-1)]
                        if stem in sentence_lower:
                            score += 0.5
                
                if score > 0:
                    scored_sentences.append((score, sentence, 'keyword'))
        
        # Strategy 3: If no scoring worked, use sentence position (earlier = potentially more relevant)
        if not scored_sentences:
            for idx, sentence in enumerate(sentences):
                if len(sentence) >= 10:
                    # Earlier sentences get slightly higher score
                    position_score = 1.0 - (idx / max(len(sentences), 1)) * 0.3
                    scored_sentences.append((position_score, sentence, 'position'))
        
        # Sort by score (highest first)
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # Select top sentences up to max_length
        selected = []
        total_length = 0
        for score, sentence, method in scored_sentences:
            sentence_with_space = sentence + " "
            if total_length + len(sentence_with_space) <= max_length:
                selected.append(sentence)
                total_length += len(sentence_with_space)
            else:
                # Try to fit partial sentence if close to max_length
                remaining = max_length - total_length
                if remaining > 50 and len(sentence) > remaining:
                    # Take first part of sentence
                    partial = sentence[:remaining].rsplit('.', 1)[0] + "."
                    if partial:
                        selected.append(partial)
                break
        
        if selected:
            snippet = " ".join(selected)
            if total_length < len(text):
                snippet += "..."
            return snippet
        
        # Final fallback: return highest scoring sentence or first sentence
        if scored_sentences:
            best_sentence = scored_sentences[0][1]
            return best_sentence[:max_length] + ("..." if len(best_sentence) > max_length else "")
        
        # Last resort: first few sentences
        snippet = " ".join(sentences[:3])[:max_length]
        if len(text) > max_length:
            snippet += "..."
        return snippet
    
    def _fuzzy_match(self, word: str, text: str, threshold: float = 0.8) -> bool:
        """
        Check if a word fuzzy-matches any word in the text.
        Handles typos like "attedece" matching "attendance".
        
        OPTIMIZED: Uses quick character overlap check before expensive SequenceMatcher.
        
        Args:
            word: The query keyword to match
            text: The text to search in (lowercase)
            threshold: Minimum similarity ratio (0.0 to 1.0)
        
        Returns:
            True if a fuzzy match is found
        """
        word_lower = word.lower()
        
        # FAST PATH: Check exact substring match first
        if word_lower in text:
            return True
        
        # For very short words (< 4 chars), only accept exact matches
        if len(word_lower) < 4:
            return False
        
        # For short words (4-5 chars), require slightly higher threshold, but not as high as 0.85
        if len(word_lower) < 6:
            threshold = max(threshold, 0.80)  # Lowered from 0.85 for better typo handling
        
        # OPTIMIZATION: Quick character set overlap check (50%+ common chars required)
        word_chars = set(word_lower)
        
        # Extract unique words from text (cached via set comprehension)
        import re
        text_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', text.lower()))  # Only words 4+ chars
        
        # Check fuzzy match against words of similar length only
        from difflib import SequenceMatcher
        
        for text_word in text_words:
            len_diff = abs(len(text_word) - len(word_lower))
            
            # Only compare words of similar length (within 2 chars)
            if len_diff > 2:
                continue
            
            # QUICK CHECK: Character overlap (must share >50% of characters)
            text_word_chars = set(text_word)
            common_chars = word_chars & text_word_chars
            min_common = min(len(word_chars), len(text_word_chars)) * 0.5
            
            if len(common_chars) < min_common:
                continue
            
            # Expensive check only if quick check passes
            ratio = SequenceMatcher(None, word_lower, text_word).ratio()
            if ratio >= threshold:
                return True
        
        return False
    
    def _extract_query_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords from a query for content relevance scoring.
        
        Removes common stop words and extracts content-bearing terms.
        
        Args:
            query: User query string
        
        Returns:
            List of keyword strings (lowercase)
        """
        import re
        
        # Common English stop words to ignore
        stop_words = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'as', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'under', 'again', 'further', 'then',
            'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
            'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
            'and', 'but', 'if', 'or', 'because', 'until', 'while', 'although',
            'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
            'am', 'it', 'its', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours',
            'you', 'your', 'he', 'him', 'his', 'she', 'her', 'they', 'them',
            'about', 'also', 'any', 'both', 'but', 'get', 'got', 'out', 'up',
            'down', 'off', 'over',
            # Spanish stop words
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del',
            'en', 'y', 'o', 'a', 'al', 'con', 'por', 'para', 'como', 'su', 'sus',
            'este', 'esta', 'estos', 'estas', 'lo', 'le', 'les', 'me', 'te', 'se',
            'nos', 'os', 'mi', 'tu', 'mì', 'tì', 'ti', 'mi', 'que', 'qué',
            'es', 'son', 'fue', 'era', 'ser', 'estar', 'han', 'había', 'habia',
            'una', 'uno', 'unas', 'unos', 'todo', 'todos', 'toda', 'todas'
        }
        
        # Split into words (support Unicode/accented characters)
        words = re.findall(r'\b[\w]+\b', query.lower(), re.UNICODE)
        
        # Filter out stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Also add 2-word phrases for better matching (skip-gram like)
        # Allows matching "procedimiento degasado" from "procedimiento de degasado"
        words_original = re.findall(r'\b[\w]+\b', query.lower(), re.UNICODE)
        for i in range(len(words_original)):
            # Find next non-stop word within 2 positions
            if words_original[i] in stop_words:
                continue
            
            # Check i+1, i+2, and i+3 to skip stop words
            for skip in range(1, 4):
                if i + skip < len(words_original):
                    next_word = words_original[i + skip]
                    if next_word not in stop_words:
                        keywords.append(f"{words_original[i]} {next_word}")
                        break  # Only add the nearest meaningful pair
                else:
                    break
        
        return keywords
    
