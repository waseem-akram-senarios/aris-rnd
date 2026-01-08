
import unittest
from unittest.mock import MagicMock, patch, ANY
import os
import sys

# Adjust path to import services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from services.retrieval.engine import RetrievalEngine
from shared.config.settings import ARISConfig

class TestMultilingualSupport(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_vectorstore = MagicMock()
        self.mock_embeddings = MagicMock()
        
        # Mock standard components
        with patch('services.retrieval.engine.VectorStoreFactory') as mock_factory, \
             patch('services.retrieval.engine.OpenAIEmbeddings', return_value=self.mock_embeddings):
            
            # Setup factory mock
            mock_factory.create_vector_store.return_value = self.mock_vectorstore
            
            self.engine = RetrievalEngine(
                use_cerebras=False,
                vector_store_type="opensearch",
                opensearch_domain="test-domain",
                opensearch_index="test-index"
            )
            
            # Inject mock multi_index_manager to avoid connection attempts
            self.mock_index_manager = MagicMock()
            self.engine.multi_index_manager = self.mock_index_manager
            
            # Setup store mock returned by index manager
            self.mock_store = MagicMock()
            self.mock_store.vectorstore = self.mock_vectorstore
            self.mock_index_manager.get_or_create_index_store.return_value = self.mock_store
            
            # Inject mock vectorstore directly as it might be initialized differently
            self.engine.vectorstore = self.mock_vectorstore
            self.engine.vector_store_type = "opensearch"
            self.engine.opensearch_index = "test-index" # Ensure fallback uses this index

    def test_filter_language_in_query_with_rag(self):
        """Verify that filter_language creates correct OpenSearch filter"""
        # Setup
        self.mock_embeddings.embed_query.return_value = [0.1] * 1536
        # Mock retriever returned by as_retriever to avoid invoke errors
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []
        mock_retriever.get_relevant_documents.return_value = []
        self.mock_vectorstore.as_retriever.return_value = mock_retriever
        
        # Test 1: Only language filter
        print("DEBUG: Calling query_with_rag")
        print(f"DEBUG: Vectorstore mock id: {id(self.mock_vectorstore)}")
        print(f"DEBUG: Engine vectorstore id: {id(self.engine.vectorstore)}")
        
        self.engine.query_with_rag(
            question="test",
            k=5,
            filter_language="spa",
            use_mmr=False,  # Simplify path first
            use_hybrid_search=False, # Force standard retriever path
            search_mode='semantic' # Prevent override
        )
        
        # Verify filter construction via as_retriever
        call_args = self.mock_vectorstore.as_retriever.call_args
        if call_args is None:
            print("DEBUG: as_retriever was NOT called")
        else:
            print(f"DEBUG: as_retriever called with: {call_args}")
            
        self.assertIsNotNone(call_args, "as_retriever not called")
        kwargs = call_args[1].get('search_kwargs', {})
        
        expected_filter = {"term": {"metadata.language.keyword": "spa"}}
        self.assertEqual(kwargs.get('filter'), expected_filter)

    def test_combined_filters(self):
        """Verify combined active_sources and filter_language"""
        self.mock_embeddings.embed_query.return_value = [0.1] * 1536
        # Mock retriever
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []
        self.mock_vectorstore.as_retriever.return_value = mock_retriever
        
        # Test 2: Language + Active Sources
        self.engine.query_with_rag(
            question="test",
            k=5,
            filter_language="fra",
            active_sources=["doc1.pdf"],
            use_mmr=False,
            use_hybrid_search=False, # Force standard retriever path
            search_mode='semantic' # Prevent override
        )
        
        call_args = self.mock_vectorstore.as_retriever.call_args
        self.assertIsNotNone(call_args, "as_retriever not called in combined test")
        
        kwargs = self.mock_vectorstore.as_retriever.call_args[1].get('search_kwargs', {})
        actual_filter = kwargs.get('filter')
        
        # In OpenSearch mode with per-doc indexes, source filtering is handled by index selection,
        # so the filter passed to retrieval should ONLY contain the language filter.
        # This means it won't be a bool/must query, but a direct term query.
        
        expected_filter = {"term": {"metadata.language.keyword": "fra"}}
        self.assertEqual(actual_filter, expected_filter)
        
        # Note: We trust that active_sources logic (tested elsewhere or implied) handles the index selection.
        # The key verification here is that language filter is PRESERVED even when active_sources is used.

    @patch('openai.OpenAI')
    @patch('services.retrieval.engine.RetrievalEngine.count_tokens', return_value=100)
    def test_openai_prompt_language(self, mock_count_tokens, mock_openai):
        """Verify OpenAI prompt receives language instruction"""
        # Setup OpenAI mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Respuesta"))]
        mock_client.chat.completions.create.return_value = mock_response
        self.engine.openai_pi_key = "fake_key"
        self.engine.openai_model = "gpt-4"
        
        # Execute
        self.engine._query_openai(
            question="Hola",
            context="Contexto",
            response_language="Spanish"
        )
        
        # Verify prompt
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        system_prompt = messages[0]['content']
        
        # Check for critical instruction
        self.assertIn("CRITICAL: You MUST answer strictly in Spanish", system_prompt)

    @patch('requests.post')
    def test_cerebras_prompt_language(self, mock_post):
        """Verify Cerebras prompt receives language instruction"""
        # Setup
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'text': 'Respuesta'}]}
        mock_post.return_value = mock_response
        self.engine.use_cerebras = True
        self.engine.cerebras_api_key = "fake"
        
        # Execute
        self.engine._query_cerebras(
            question="Hola",
            context="Contexto",
            response_language="German"
        )
        
        # Verify prompt
        call_args = mock_post.call_args
        json_data = call_args[1]['json']
        prompt = json_data['prompt']
        
        # Check for instruction
        self.assertIn("CRITICAL: You MUST answer strictly in German", prompt)

if __name__ == '__main__':
    unittest.main()
