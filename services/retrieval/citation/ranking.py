"""
Citation deduplication and relevance ranking.

Extracted from engine.py for maintainability.
This mixin is inherited by RetrievalEngine.
"""
import re
import logging
from typing import List, Dict, Optional

from shared.config.settings import ARISConfig

logger = logging.getLogger(__name__)

class CitationRankingMixin:
    """Mixin providing citation deduplication and relevance ranking capabilities."""
    
    def _deduplicate_citations(self, citations: List[Dict]) -> List[Dict]:
        """
        Merge duplicate citations (same source + page).
        Combines snippets intelligently and preserves best metadata.
        
        Args:
            citations: List of citation dictionaries
        
        Returns:
            Deduplicated list of citations with updated IDs
        """
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if not citations:
            return []
        
        # Group citations by (source, page) tuple
        # Ensure all citations have page numbers before grouping
        citation_groups = {}
        import os
        for citation in citations:
            source = citation.get('source', 'Unknown')
            # Normalize source (take basename to avoid path vs filename duplicates)
            if source and ('/' in source or '\\' in source):
                source = os.path.basename(source)
            page = citation.get('page')
            # Ensure page is always set (fallback to 1)
            if page is None or page < 1:
                page = 1
                citation['page'] = 1
                citation['page_confidence'] = citation.get('page_confidence', 0.1)
                logger.debug(f"Deduplication: Citation missing page, set to 1 for source '{source}'")
            key = (source, page)
            
            if key not in citation_groups:
                citation_groups[key] = []
            citation_groups[key].append(citation)
        
        # Merge citations in each group
        merged_citations = []
        for group_key, group_citations in citation_groups.items():
            if len(group_citations) == 1:
                # No duplicates, keep as is but use normalized source
                citation = group_citations[0]
                citation['source'] = group_key[0]
                merged_citations.append(citation)
            else:
                # Merge duplicates - keep citation with highest confidence
                # PRIORITY: Citations with image_ref (visual proof) > High confidence scores
                best_citation = max(group_citations, key=lambda c: (
                    1.0 if c.get('image_ref') else 0.0,  # Prefer citations with visual references
                    c.get('source_confidence', 0) + c.get('page_confidence', 0)
                ))
                
                # Merge snippets - combine unique portions
                all_snippets = [c.get('snippet', '') for c in group_citations if c.get('snippet')]
                if all_snippets:
                    # Use longest snippet (most context) OR snippet with page markers
                    def snippet_score(s):
                        score = len(s)
                        if '--- Page' in s: score += 2000  # Strong preference for page markers
                        if 'Image' in s and 'Page' in s: score += 1000  # Preference for image+page context
                        return score
                    
                    best_snippet = max(all_snippets, key=snippet_score)
                    # If snippets are very different, combine them
                    if len(set(all_snippets)) > 1:
                        # Try to merge non-overlapping snippets
                        combined = best_snippet
                        for snippet in all_snippets:
                            if snippet not in combined and len(snippet) > 50:
                                # Add if it adds significant new content
                                combined += " ... " + snippet[:200]
                        best_snippet = combined[:500]  # Limit total length
                    best_citation['snippet'] = best_snippet
                
                # Preserve best metadata from all citations
                best_citation['source'] = group_key[0] # Use normalized source (basename)
                best_citation['source_confidence'] = max(
                    c.get('source_confidence', 0) for c in group_citations
                )
                best_citation['page_confidence'] = max(
                    c.get('page_confidence', 0) for c in group_citations
                )
                
                # Ensure page is always set (double-check after merge)
                if best_citation.get('page') is None or best_citation.get('page') < 1:
                    best_citation['page'] = group_key[1] if group_key[1] else 1
                    best_citation['page_confidence'] = best_citation.get('page_confidence', 0.1)
                    logger.debug(f"Deduplication: Merged citation missing page, set to {best_citation['page']}")
                
                # Merge other metadata if available
                if any(c.get('section') for c in group_citations):
                    sections = [c.get('section') for c in group_citations if c.get('section')]
                    best_citation['section'] = sections[0] if sections else None
                
                merged_citations.append(best_citation)
                logger.debug(f"Merged {len(group_citations)} duplicate citations for {group_key}")
        
        # Re-number IDs sequentially and ensure all citations have page numbers
        for i, citation in enumerate(merged_citations, 1):
            citation['id'] = i
            # Final check: ensure page is always set
            if citation.get('page') is None or citation.get('page') < 1:
                citation['page'] = 1
                citation['page_confidence'] = citation.get('page_confidence', 0.1)
                logger.warning(f"Deduplication: Final citation {i} missing page, set to 1")
        
        logger.info(f"Deduplicated citations: {len(citations)} -> {len(merged_citations)}")
        return merged_citations
    
    def _count_flexible_keyword_matches(self, keywords: List[str], text: str) -> float:
        """
        Count keyword matches with flexible substring matching.
        
        Handles abbreviations automatically:
        - "kube" matches "kubernetes" (substring match)
        - "k8s" matches "kubernetes" (if k8s appears in text)
        - Exact matches get full weight (1.0)
        - Substring matches get partial weight (0.7)
        
        Args:
            keywords: List of query keywords
            text: Text to search in
        
        Returns:
            Weighted match score
        """
        import re
        matches = 0.0
        text_lower = text.lower()
        
        # Extract all words from text for substring checking
        text_words = set(re.findall(r'\b\w+\b', text_lower))
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Exact word match (highest priority)
            # Check for word boundaries to ensure exact match
            if re.search(r'\b' + re.escape(keyword_lower) + r'\b', text_lower):
                matches += 1.0
            # Substring match for short keywords (3-5 chars) in longer words
            elif 3 <= len(keyword_lower) <= 5:
                # Check if keyword appears as substring in any word
                for word in text_words:
                    if keyword_lower in word and len(word) > len(keyword_lower):
                        matches += 0.7  # Partial credit for substring match
                        break  # Count once per keyword
        
        return matches
    
    def _rank_citations_by_relevance(self, citations: List[Dict], query: str) -> List[Dict]:
        """
        Rank citations by relevance to query - most relevant first.
        
        ENHANCED: When RRF/position-based scores are detected (nearly identical scores),
        use keyword-based content relevance to re-rank citations.
        
        Args:
            citations: List of citation dictionaries with similarity_score field
            query: User query string (used for keyword matching and logging)
        
        Returns:
            Ranked list of citations sorted by relevance (most relevant first)
        """
        import re
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if not citations or not query:
            return citations
        
        # STEP 1: Calculate query-content relevance score for each citation
        # This helps when RRF scores are nearly identical
        query_keywords = self._extract_query_keywords(query)
        logger.info(f"📊 [CITATION_RANK] Query keywords: {query_keywords}")
        
        # Separate phrases from single keywords for stricter matching
        phrase_keywords = [kw for kw in query_keywords if ' ' in kw]
        single_keywords = [kw for kw in query_keywords if ' ' not in kw]
        
        for citation in citations:
            # CRITICAL FIX: Only use SNIPPET for relevance scoring, not full_text
            # full_text may contain unrelated content from the same page
            # The snippet is what's actually shown to the user and should be relevant
            snippet = citation.get('snippet', '') or ''
            # Only use full_text if snippet is too short (< 50 chars)
            if len(snippet) < 50:
                content = (citation.get('full_text', '') or '') + ' ' + snippet
            else:
                content = snippet
            content_lower = content.lower()
            
            # Count keyword matches with phrase weighting
            # STRICT: Phrase matches are REQUIRED for relevance when phrases exist in query
            keyword_matches = 0
            phrase_matches = 0
            matched_keywords = []
            context_valid_single_matches = 0  # Single keywords that appear in relevant context
            
            # STEP 1: Check phrase matches FIRST (most important)
            for kw in phrase_keywords:
                if kw.lower() in content_lower:
                    keyword_matches += 1
                    phrase_matches += 1
                    matched_keywords.append(kw)
                else:
                    # Check if all words in phrase appear close together (within 50 chars)
                    phrase_words = kw.split()
                    if len(phrase_words) >= 2:
                        # Find positions of each word
                        import re
                        positions = []
                        for pw in phrase_words:
                            matches = list(re.finditer(r'\b' + re.escape(pw.lower()) + r'\b', content_lower))
                            if matches:
                                positions.append([m.start() for m in matches])
                            else:
                                positions.append([])
                        
                        # Check if words appear close together (proximity match)
                        if all(positions):
                            # Check all combinations for proximity
                            found_proximity = False
                            for pos1 in positions[0]:
                                for pos2 in positions[-1]:
                                    if abs(pos1 - pos2) < 100:  # Within 100 chars
                                        found_proximity = True
                                        break
                                if found_proximity:
                                    break
                            
                            if found_proximity:
                                keyword_matches += 1
                                phrase_matches += 1
                                matched_keywords.append(kw + " (proximity)")
            
            # STEP 2: Check single keywords, but validate context
            for kw in single_keywords:
                kw_lower = kw.lower()
                # Check if keyword exists
                if self._fuzzy_match(kw, content_lower, threshold=0.70):
                    keyword_matches += 1
                    matched_keywords.append(kw)
                    
                    # CONTEXT VALIDATION: Check if keyword appears in relevant context
                    # For ambiguous words like "leave", check surrounding words
                    import re
                    pattern = r'.{0,30}\b' + re.escape(kw_lower) + r'\b.{0,30}'
                    contexts = re.findall(pattern, content_lower)
                    
                    # Check if any context contains other query keywords
                    for ctx in contexts:
                        other_keywords = [k for k in single_keywords if k != kw]
                        if any(ok.lower() in ctx for ok in other_keywords):
                            context_valid_single_matches += 1
                            break
                        # Also check if phrase keywords' words appear in context
                        for pk in phrase_keywords:
                            pk_words = pk.split()
                            if any(pkw.lower() in ctx for pkw in pk_words):
                                context_valid_single_matches += 1
                                break
            
            # Calculate content relevance score (0.0 to 1.0)
            # STRICT SCORING: Phrase matches are weighted 3x, context-valid singles 1.5x
            weighted_matches = (phrase_matches * 3) + (context_valid_single_matches * 1.5) + ((keyword_matches - phrase_matches - context_valid_single_matches) * 0.5)
            max_possible = (len(phrase_keywords) * 3) + (len(single_keywords) * 1.5)
            
            content_relevance = weighted_matches / max(max_possible, 1)
            
            # STRICT FILTERING: Require phrase match OR multiple keyword matches for relevance
            # Single keyword match alone is NOT enough (prevents "leave lights" matching "leave policy")
            has_phrase_match = phrase_matches >= 1
            has_multiple_keywords = keyword_matches >= 2
            has_context_valid_match = context_valid_single_matches >= 1
            
            is_truly_relevant = has_phrase_match or has_multiple_keywords or has_context_valid_match
            
            if not is_truly_relevant:
                # Single keyword match without context - mark as IRRELEVANT
                content_relevance = 0.0
                logger.debug(f"Citation REJECTED (single keyword, no context): {matched_keywords}")
            elif not has_phrase_match and keyword_matches == 1:
                # Only 1 keyword match but has context - low relevance
                content_relevance = 0.15
                logger.debug(f"Citation kept with context-valid single match: {matched_keywords}")
            
            citation['_content_relevance'] = content_relevance
            citation['_matched_keywords'] = matched_keywords
            citation['_phrase_matches'] = phrase_matches
            
            # Log relevance for debugging
            source = citation.get('source', 'Unknown')[:30]
            logger.debug(f"Citation from {source}: relevance={content_relevance:.2f}, matched={matched_keywords}, phrases={phrase_matches}, context_valid={context_valid_single_matches}")
        
        # STEP 2: Filter out completely irrelevant citations (0 keyword matches)
        # ACTUALLY REMOVE irrelevant citations - don't just move them to the end
        relevant_citations = [c for c in citations if c.get('_content_relevance', 0) > 0]
        irrelevant_citations = [c for c in citations if c.get('_content_relevance', 0) == 0]
        
        if relevant_citations:
            # We have relevant citations - REMOVE the irrelevant ones entirely
            if irrelevant_citations:
                logger.info(f"📊 [CITATION_FILTER] REMOVING {len(irrelevant_citations)} irrelevant citations "
                           f"(keeping only {len(relevant_citations)} relevant ones)")
                for irr in irrelevant_citations[:3]:  # Log first 3 removed
                    logger.debug(f"   Removed: {irr.get('source', 'Unknown')[:40]} (0 keyword matches)")
            citations = relevant_citations  # ONLY keep relevant citations
        else:
            # No relevant citations found - keep all but warn
            logger.warning(f"📊 [CITATION_FILTER] No citations matched query keywords! Keeping all {len(citations)} citations.")
        
        # ── Check if rerank_scores are available (highest quality signal) ──
        rerank_scores = [c.get('rerank_score') for c in citations if c.get('rerank_score') is not None]
        has_rerank = len(rerank_scores) > 0 and len(rerank_scores) >= len(citations) * 0.5  # At least half have rerank
        
        # Check if we have similarity scores
        similarity_scores = [c.get('similarity_score') for c in citations if c.get('similarity_score') is not None]
        
        if not similarity_scores:
            logger.warning("No similarity scores found in citations. Using content relevance for ranking.")
            # Sort by content relevance only
            citations.sort(key=lambda c: -c.get('_content_relevance', 0))
            return citations
        
        # ── F6 FIX: When rerank_scores are available, use them directly for ranking & percentages ──
        # FlashRank scores are 0-1 cross-encoder relevance. Much more reliable than RRF or position-based.
        if has_rerank:
            logger.info(f"📊 [CITATION_RANK] Using FlashRank rerank_scores for ranking ({len(rerank_scores)}/{len(citations)} citations)")
            
            # Sort by rerank_score (descending), fall back to content relevance
            citations.sort(key=lambda c: (
                -(c.get('rerank_score') or 0),
                -c.get('_content_relevance', 0),
                c.get('id', 0)
            ))
            
            # Calculate percentages from rerank_score (0-1 → 0-100%)
            best_rerank = max(rerank_scores) if rerank_scores else 1.0
            for idx, citation in enumerate(citations):
                rs = citation.get('rerank_score')
                if rs is not None and best_rerank > 0:
                    # Normalize relative to best: best gets 100%, others proportionally less
                    pct = (rs / best_rerank) * 100.0
                    citation['similarity_percentage'] = round(max(5.0, pct), 1)
                elif citation.get('_content_relevance', 0) > 0:
                    citation['similarity_percentage'] = round(max(10.0, 40.0 - (idx * 5)), 1)
                else:
                    citation['similarity_percentage'] = round(max(5.0, 20.0 - (idx * 3)), 1)
                citation['id'] = idx + 1
            
            top_3 = [(c.get('source', 'Unknown')[:25], f"rerank={c.get('rerank_score', 0):.3f}", f"{c.get('similarity_percentage', 0):.0f}%") for c in citations[:3]]
            logger.info(f"📊 [CITATION_RANK] Ranked by FlashRank rerank_score. Top 3: {top_3}")
            
            # CLEANUP
            for citation in citations:
                for field in ['_content_relevance', '_matched_keywords', '_phrase_matches']:
                    citation.pop(field, None)
            return citations
        
        # ── No rerank scores: detect score type and rank accordingly ──
        min_score = min(similarity_scores)
        max_score = max(similarity_scores)
        
        # Detect RRF scores (very small, closely packed scores like 0.004...)
        is_rrf_scores = max_score < 0.05 and (max_score - min_score) < 0.01
        
        # Detect MIXED scoring systems (some high ~0.8, some low ~0.004)
        is_mixed_scores = max_score > 0.5 and min_score < 0.05 and len(similarity_scores) > 1
        
        is_position_based = (max_score <= 1.0 and min_score >= 0.5 and 
                            (max_score - min_score) < 0.5 and len(similarity_scores) > 1)
        is_distance_based = max_score > 1.0 and min_score > 0.5 and not is_position_based
        
        if is_mixed_scores or is_rrf_scores:
            score_type = "mixed" if is_mixed_scores else "RRF"
            logger.warning(f"📊 [CITATION_RANK] Detected {score_type} scores (range: {min_score:.4f}-{max_score:.4f}). "
                          f"Using CONTENT RELEVANCE as PRIMARY ranking factor.")
            citations.sort(key=lambda c: (
                -c.get('_content_relevance', 0),
                -c.get('similarity_score', 0) if c.get('similarity_score') is not None else 999,
                c.get('id', 0)
            ))
            max_relevance = max([c.get('_content_relevance', 0) for c in citations]) if citations else 0
            
            for idx, citation in enumerate(citations):
                relevance = citation.get('_content_relevance', 0)
                if idx == 0 and relevance > 0:
                    citation['similarity_percentage'] = 100.0
                elif relevance > 0:
                    if max_relevance > 0:
                        relative_relevance = relevance / max_relevance
                        citation['similarity_percentage'] = round(50.0 + (relative_relevance * 45.0), 1)
                    else:
                        citation['similarity_percentage'] = round(90.0 - (idx * 10), 1)
                else:
                    citation['similarity_percentage'] = round(max(10.0, 30.0 - (idx * 5)), 1)
                citation['id'] = idx + 1
            
            top_3 = [(c.get('source', 'Unknown')[:25], f"rel={c.get('_content_relevance', 0):.2f}", f"{c.get('similarity_percentage', 0):.0f}%") for c in citations[:3]]
            logger.info(f"📊 [CITATION_RANK] Ranked by content relevance. Top 3: {top_3}")
            
            for citation in citations:
                for field in ['_content_relevance', '_matched_keywords', '_phrase_matches']:
                    citation.pop(field, None)
            return citations
        
        if is_position_based:
            logger.warning(f"Detected position-based fallback scores (range: {min_score:.3f}-{max_score:.3f}). "
                          f"Actual similarity scores may not be available. Consider using similarity_search_with_score.")
        
        # Sort by similarity score with enhanced tie-breaking
        # For distance-based scores (lower = more similar), sort ascending
        # For similarity-based scores (higher = more similar), sort descending
        # Enhanced: Use page_confidence and source_confidence as tie-breakers for better accuracy
        if is_distance_based:
            # Distance-based: lower score = more similar, so sort ascending
            citations.sort(key=lambda c: (
                c.get('similarity_score', 999) if c.get('similarity_score') is not None else 999,  # Primary: similarity (ascending for distance)
                -c.get('page_confidence', 0.0),  # Secondary: higher page confidence = better (descending)
                -c.get('source_confidence', 0.0),  # Tertiary: higher source confidence = better (descending)
                c.get('id', 0)  # Quaternary: original order (ascending) for final tie-breaking
            ))
            logger.debug(f"Sorted citations by distance-based similarity with confidence tie-breakers")
        else:
            # Similarity-based: higher score = more similar, so sort descending
            citations.sort(key=lambda c: (
                -c.get('similarity_score', -999) if c.get('similarity_score') is not None else 999,  # Primary: similarity (descending for similarity)
                -c.get('page_confidence', 0.0),  # Secondary: higher page confidence = better (descending)
                -c.get('source_confidence', 0.0),  # Tertiary: higher source confidence = better (descending)
                c.get('id', 0)  # Quaternary: original order (ascending) for final tie-breaking
            ))
            logger.debug(f"Sorted citations by similarity-based score with confidence tie-breakers")
        
        # Get sorted scores for validation and percentage calculation
        sorted_scores = [c.get('similarity_score') for c in citations if c.get('similarity_score') is not None]
        
        # Validate sorting is correct
        if citations and sorted_scores and len(sorted_scores) > 1:
            if is_distance_based:
                # For distance: scores should increase (first is lowest/most similar)
                is_sorted = all(sorted_scores[i] <= sorted_scores[i+1] for i in range(len(sorted_scores)-1))
            else:
                # For similarity: scores should decrease (first is highest/most similar)
                is_sorted = all(sorted_scores[i] >= sorted_scores[i+1] for i in range(len(sorted_scores)-1))
            
            if not is_sorted:
                logger.warning("Citations not properly sorted by similarity! Re-sorting...")
                if is_distance_based:
                    citations.sort(key=lambda c: c.get('similarity_score', 999) if c.get('similarity_score') is not None else 999)
                else:
                    citations.sort(key=lambda c: -c.get('similarity_score', -999) if c.get('similarity_score') is not None else 999)
                # Re-get sorted scores after re-sorting
                sorted_scores = [c.get('similarity_score') for c in citations if c.get('similarity_score') is not None]
        
        # Calculate similarity percentages (100% for most similar, decreasing for others)
        # Get the best (most similar) score to use as 100% baseline
        if sorted_scores and len(sorted_scores) > 0:
            if is_distance_based:
                # For distance: best score is the minimum (lowest distance = most similar)
                best_score = min(sorted_scores)
                worst_score = max(sorted_scores)
            else:
                # For similarity: best score is the maximum (highest similarity = most similar)
                best_score = max(sorted_scores)
                worst_score = min(sorted_scores)
            
            # Calculate percentage for each citation
            # Use absolute value to handle both positive and negative ranges
            score_range = abs(worst_score - best_score) if worst_score != best_score else 0.0
            
            # IMPROVED: Detect if scores are from mixed systems (e.g., RRF 0.01 + similarity 0.85)
            # OR if scores are so close that percentage calculation gives misleading results
            use_rank_based = False
            scores_are_similar = False
            
            if len(sorted_scores) > 1 and best_score > 0:
                ratio = best_score / max(worst_score, 0.0001)
                # Relative range: if score_range is < 10% of the best_score, scores are very close
                relative_range = score_range / best_score if best_score > 0 else 0
                
                # Case 1: Mixed scoring systems (ratio > 50x OR one score >> other)
                if ratio > 50 or (best_score > 0.1 and worst_score < 0.01):
                    use_rank_based = True
                    logger.warning(f"Detected mixed scoring systems (ratio={ratio:.1f}). Using rank-based percentages.")
                
                # Case 2: Scores are very close together (relative range < 10%)
                # This prevents 100% vs 0% when scores are actually similar
                elif relative_range < 0.15:
                    scores_are_similar = True
                    logger.info(f"Scores are very close (relative_range={relative_range:.3f}). Using similar-score percentages.")
            
            logger.info(f"Calculating percentages: best={best_score:.4f}, worst={worst_score:.4f}, range={score_range:.4f}, is_distance={is_distance_based}, num_scores={len(sorted_scores)}, rank_based={use_rank_based}, similar_scores={scores_are_similar}")
            
            # Calculate percentages for all citations
            num_citations = len(citations)
            for idx, citation in enumerate(citations):
                sim_score = citation.get('similarity_score')
                if sim_score is not None:
                    # FIXED: Use rank-based percentage when mixed scoring systems are detected
                    if use_rank_based:
                        # Use rank-based percentage: rank 1 = 100%, decreasing by even steps
                        # This provides more meaningful percentages when scores are from different systems
                        if num_citations == 1:
                            similarity_percentage = 100.0
                        else:
                            # Exponential decay based on rank: 100% -> ~50% -> ~25% -> ...
                            # Or linear: 100%, 90%, 80%... depending on num_citations
                            # Use a curve that doesn't go below 30% for top results
                            similarity_percentage = max(30.0, 100.0 - (idx * (70.0 / max(num_citations - 1, 1))))
                        citation['similarity_percentage'] = round(similarity_percentage, 2)
                        logger.debug(f"Citation rank {idx+1}: Using rank-based percentage {similarity_percentage:.1f}%")
                    elif scores_are_similar:
                        # Scores are very close - use a gentler falloff starting from 100%
                        # First citation gets 100%, subsequent ones decrease gently (95%, 90%, 85%...)
                        if idx == 0:
                            similarity_percentage = 100.0
                        else:
                            similarity_percentage = max(70.0, 100.0 - (idx * 5.0))
                        citation['similarity_percentage'] = round(similarity_percentage, 2)
                        logger.debug(f"Citation rank {idx+1}: Using similar-score percentage {similarity_percentage:.1f}%")
                    elif score_range < 0.0001:
                        # All scores are essentially equal - give 100% to first (best) citation, 95% to others
                        if idx == 0:
                            citation['similarity_percentage'] = 100.0
                        else:
                            citation['similarity_percentage'] = 95.0
                        logger.debug(f"Citation {citation.get('id')}: All scores equal, assigning {citation['similarity_percentage']}%")
                    elif is_distance_based:
                        # For distance: lower score = higher percentage
                        # Invert: (worst - current) / (worst - best) * 100
                        similarity_percentage = ((worst_score - sim_score) / score_range) * 100.0
                        # Ensure percentage is in valid range
                        similarity_percentage = max(0.0, min(100.0, similarity_percentage))
                        citation['similarity_percentage'] = round(similarity_percentage, 2)
                    else:
                        # For similarity: higher score = higher percentage
                        # Normalize: (current - worst) / (best - worst) * 100
                        similarity_percentage = ((sim_score - worst_score) / score_range) * 100.0
                        # Ensure percentage is in valid range
                        similarity_percentage = max(0.0, min(100.0, similarity_percentage))
                        citation['similarity_percentage'] = round(similarity_percentage, 2)
                    
                    # Debug logging for all citations to see what's happening
                    if citation.get('id', 0) <= 6 or idx <= 5:
                        sim_pct = citation.get('similarity_percentage')
                        sim_pct_str = f"{sim_pct:.2f}%" if sim_pct is not None else "N/A"
                        logger.info(f"Citation {idx+1}: score={sim_score:.4f}, calculated_percentage={sim_pct_str}, source={citation.get('source', 'Unknown')[:40]}")
                    
                    # VALIDATION: First citation should never be 0% unless there's an error
                    if idx == 0 and citation.get('similarity_percentage', 0) == 0.0 and sim_score is not None:
                        logger.error(f"⚠️ BUG DETECTED: First citation has 0% similarity despite having score={sim_score:.4f}. "
                                   f"best={best_score:.4f}, worst={worst_score:.4f}, range={score_range:.4f}. "
                                   f"Forcing to 100% to prevent misleading display.")
                        citation['similarity_percentage'] = 100.0
                else:
                    citation['similarity_percentage'] = 0.0  # No score = 0%
                    logger.warning(f"⚠️ Citation {citation.get('id')} has no similarity_score (None), setting percentage to 0%. "
                                 f"This may indicate a problem with retrieval or reranking. Citation source: {citation.get('source', 'Unknown')[:50]}")
        else:
            # No scores available - set all to 0%
            logger.warning("No similarity scores available for percentage calculation")
            for citation in citations:
                citation['similarity_percentage'] = 0.0
        
        # Re-number IDs after sorting (1 = most similar, highest similarity score)
        for i, citation in enumerate(citations, 1):
            citation['id'] = i
            # Log top 3 for debugging
            if i <= 3:
                sim_score = citation.get('similarity_score', 'N/A')
                sim_percent = citation.get('similarity_percentage', 'N/A')
                sim_str = f"{sim_score:.4f}" if isinstance(sim_score, (int, float)) else str(sim_score)
                logger.debug(f"Rank {i}: similarity={sim_str} ({sim_percent}%), "
                            f"source={citation.get('source', 'Unknown')[:50]}")
        
        top_3_scores = [f'{c.get("similarity_score", "N/A")} ({c.get("similarity_percentage") or 0:.1f}%)' for c in citations[:3]]
        logger.info(f"Ranked {len(citations)} citations by similarity (highest to lowest). Top 3: {top_3_scores}")
        
        # CLEANUP: Remove internal fields before returning (they shouldn't be in API response)
        internal_fields = ['_content_relevance', '_matched_keywords', '_phrase_matches']
        for citation in citations:
            for field in internal_fields:
                citation.pop(field, None)
        
        return citations
    
