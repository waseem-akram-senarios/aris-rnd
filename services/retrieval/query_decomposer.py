"""
Query Decomposition Module for Agentic RAG
Decomposes complex user queries into multiple specific sub-queries for better retrieval
"""
import os
import logging
from typing import List, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class QueryDecomposer:
    """
    Decomposes complex queries into sub-queries for multi-query retrieval.
    """
    
    def __init__(self, llm_model: str, openai_api_key: Optional[str] = None):
        """
        Initialize query decomposer.
        
        Args:
            llm_model: LLM model to use for decomposition (e.g., 'gpt-4o')
            openai_api_key: OpenAI API key (if None, uses env var)
        """
        self.llm_model = llm_model
        api_key = openai_api_key or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key is required for query decomposition")
        self.openai_client = OpenAI(api_key=api_key)
    
    def decompose_query(self, question: str, max_subqueries: int = 4) -> List[str]:
        """
        Decompose a complex query into specific sub-queries.
        
        Args:
            question: The original user question
            max_subqueries: Maximum number of sub-queries to generate (default: 4)
        
        Returns:
            List of sub-queries (or [original_query] if decomposition not needed/fails)
        """
        if not question or not question.strip():
            return [question]
        
        # Check if query is simple enough (single question, short)
        if self._is_simple_query(question):
            logger.info(f"Query is simple, skipping decomposition: {question[:50]}...")
            return [question]
        
        try:
            logger.info(f"Decomposing query: {question[:100]}...")
            
            # Call LLM for decomposition
            sub_queries = self._call_llm_for_decomposition(question, max_subqueries)
            
            # Validate and clean sub-queries
            validated_queries = self._validate_subqueries(sub_queries, question)
            
            if len(validated_queries) > 1:
                logger.info(f"Query decomposed into {len(validated_queries)} sub-queries")
                return validated_queries
            else:
                logger.info("Decomposition resulted in single query, using original")
                return [question]
                
        except Exception as e:
            logger.warning(f"Query decomposition failed: {e}. Using original query.")
            return [question]
    
    def _is_simple_query(self, question: str) -> bool:
        """
        Check if query is simple enough to skip decomposition.
        
        Simple queries are:
        - Very short (< 30 chars)
        - Single question mark
        - No conjunctions (and, or, but, also)
        """
        question_lower = question.lower().strip()
        
        # Very short queries (increased to 60 to cover typical "what is X" questions)
        if len(question_lower) < 60:
            return True
        
        # Check for multiple question indicators
        question_marks = question.count('?')
        if question_marks > 1:
            return False
        
        # Check for conjunctions that suggest multiple parts
        conjunctions = [' and ', ' or ', ' but ', ' also ', ' plus ', ' as well as ']
        if any(conj in question_lower for conj in conjunctions):
            return False
        
        # Check for multiple verbs/questions
        question_words = ['what', 'how', 'why', 'when', 'where', 'who', 'which']
        question_word_count = sum(1 for word in question_words if word in question_lower)
        if question_word_count > 1:
            return False
        
        return True
    
    def _call_llm_for_decomposition(self, question: str, max_subqueries: int) -> List[str]:
        """
        Call LLM to decompose the query.
        
        Args:
            question: Original question
            max_subqueries: Maximum number of sub-queries
        
        Returns:
            List of sub-queries
        """
        # Detect if this is a summary query
        question_lower = question.lower()
        is_summary_query = any(kw in question_lower for kw in 
                              ['summary', 'summarize', 'overview', 'what is this document about',
                               'what does this document contain', 'what is in this document',
                               'tell me about', 'describe', 'explain this document'])
        
        if is_summary_query:
            system_prompt = """You are a query decomposition assistant specialized in document summaries. 
Break down summary requests into specific aspects that would help create a comprehensive summary.

For summary queries, decompose into:
1. What is the document about? (main topic/theme)
2. What are the key points? (important information)
3. What are the main topics covered? (subject areas)
4. What important details are included? (specifics)

Return 3-4 specific sub-questions, one per line, no numbering or bullets.
Maximum {max_subqueries} sub-questions.

Examples:
Input: "Give me summary of this document"
Output:
What is the document about?
What are the key points?
What are the main topics covered?
What important details are included?

Input: "What is this document about?"
Output:
What is the main topic of the document?
What are the key points covered?
What important information does it contain?""".format(max_subqueries=max_subqueries)
        else:
            system_prompt = """You are a query decomposition assistant. Your task is to break down complex questions into 2-4 specific sub-questions that would help answer the original question comprehensively.

Rules:
1. Only decompose if the question has multiple parts or aspects
2. Each sub-question should target a specific aspect of the original question
3. Sub-questions should be independent and answerable
4. If the question is already specific and simple, return it as-is
5. Return ONLY the sub-questions, one per line, no numbering or bullets
6. Maximum {max_subqueries} sub-questions

Examples:
Input: "What are the specifications and safety requirements?"
Output:
What are the specifications?
What are the safety requirements?

Input: "How does the system work and what are its benefits?"
Output:
How does the system work?
What are the benefits of the system?

Input: "What is artificial intelligence?"
Output:
What is artificial intelligence?""".format(max_subqueries=max_subqueries)
        
        user_prompt = f"""Decompose this question into specific sub-questions:

Question: {question}

Provide 2-4 specific sub-questions (one per line) that would help answer this comprehensively. If the question is already simple and specific, return it unchanged."""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent decomposition
                max_tokens=200
            )
            
            if not response.choices or not response.choices[0].message.content:
                raise ValueError("Empty response from LLM")
            
            content = response.choices[0].message.content.strip()
            
            # Parse sub-queries (one per line)
            sub_queries = [q.strip() for q in content.split('\n') if q.strip()]
            
            # Remove numbering/bullets if present
            cleaned_queries = []
            for q in sub_queries:
                # Remove leading numbers, bullets, dashes
                q = q.lstrip('0123456789.-) ').strip()
                if q:
                    cleaned_queries.append(q)
            
            return cleaned_queries if cleaned_queries else [question]
            
        except Exception as e:
            logger.error(f"Error calling LLM for decomposition: {e}")
            raise
    
    def _validate_subqueries(self, sub_queries: List[str], original_question: str) -> List[str]:
        """
        Validate and clean sub-queries.
        
        Args:
            sub_queries: List of sub-queries from LLM
            original_question: Original question for fallback
        
        Returns:
            Validated list of sub-queries
        """
        if not sub_queries:
            return [original_question]
        
        validated = []
        for query in sub_queries:
            query = query.strip()
            # Remove empty queries
            if not query:
                continue
            # Remove queries that are too short (likely parsing errors)
            if len(query) < 10:
                continue
            # Remove queries that are just the original (duplicate)
            if query.lower() == original_question.lower():
                continue
            validated.append(query)
        
        # If validation removed all queries, return original
        if not validated:
            return [original_question]
        
        # Limit to max_subqueries
        return validated[:len(sub_queries)]

