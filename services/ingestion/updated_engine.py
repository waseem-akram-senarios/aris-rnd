
import os
import logging
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from shared.utils.local_embeddings import LocalHashEmbeddings
from vectorstores.vector_store_factory import VectorStoreFactory
from shared.config.settings import ARISConfig

# Set up logging
logger = logging.getLogger(__name__)

load_dotenv()

class IngestionEngine:
    def __init__(self, use_cerebras=False, metrics_collector=None, 
                 embedding_model=None,
                 openai_model=None,
                 cerebras_model=None,
                 vector_store_type="opensearch",
                 opensearch_domain=None,
                 opensearch_index=None,
                 chunk_size=None,
                 chunk_overlap=None):
        self.use_cerebras = use_cerebras
        
        # Store model selections - use ARISConfig defaults if not provided
        if embedding_model is None:
            embedding_model = ARISConfig.EMBEDDING_MODEL
        if openai_model is None:
            openai_model = ARISConfig.OPENAI_MODEL
        if cerebras_model is None:
            cerebras_model = ARISConfig.CEREBRAS_MODEL
        
        self.embedding_model = embedding_model
        self.openai_model = openai_model
        self.cerebras_model = cerebras_model
        
        # Vector store configuration - REQUIRE OpenSearch or PGVector
        self.vector_store_type = vector_store_type.lower()
        if self.vector_store_type not in ['opensearch', 'pgvector']:
            raise ValueError(
                f"Vector store type must be 'opensearch' or 'pgvector'. Got '{vector_store_type}'. "
                f"Please set VECTOR_STORE_TYPE in .env to 'opensearch' or 'pgvector'."
            )
        
        # Validate OpenSearch or PGVector domain - REQUIRED, no fallback
        if self.vector_store_type == 'opensearch':
            if not opensearch_domain or len(str(opensearch_domain).strip()) < 3:
                opensearch_domain = ARISConfig.AWS_OPENSEARCH_DOMAIN
                if not opensearch_domain or len(str(opensearch_domain).strip()) < 3:
                    raise ValueError(
                        f"OpenSearch domain is required. Please set AWS_OPENSEARCH_DOMAIN in .env file. "
                        f"Got: '{opensearch_domain}'"
                    )
            self.opensearch_domain = str(opensearch_domain).strip()
            self.opensearch_index = opensearch_index or ARISConfig.AWS_OPENSEARCH_INDEX
        elif self.vector_store_type == 'pgvector':
            # For PGVector, ensure the domain and index configurations exist
            self.pgvector_domain = ARISConfig.PGVECTOR_DOMAIN
            self.pgvector_index = ARISConfig.PGVECTOR_INDEX
            if not self.pgvector_domain or len(str(self.pgvector_domain).strip()) < 3:
                raise ValueError(
                    f"PGVector domain is required. Please set PGVECTOR_DOMAIN in .env file."
                )
        
        # Initialize embeddings
        if os.getenv('OPENAI_API_KEY'):
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
        else:
            self.embeddings = LocalHashEmbeddings(model_name=self.embedding_model)
        
        # Initialize vectorstore (OpenSearch or PGVector)
        self.vectorstore = None
        if self.vector_store_type == 'opensearch':
            from vectorstores.opensearch_store import OpenSearchVectorStore
            self.vectorstore = OpenSearchVectorStore(
                embeddings=self.embeddings,
                domain=self.opensearch_domain,
                index_name=self.opensearch_index
            )
        elif self.vector_store_type == 'pgvector':
            from vectorstores.pgvector_store import PgVectorStore  # Ensure you have this class implemented
            self.vectorstore = PgVectorStore(
                embeddings=self.embeddings,
                domain=self.pgvector_domain,
                index_name=self.pgvector_index
            )
        
        # Set up chunking configuration
        self.chunk_size = chunk_size or ARISConfig.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or ARISConfig.DEFAULT_CHUNK_OVERLAP
        
        # Initialize metrics collector
        self.metrics_collector = metrics_collector
        if self.metrics_collector is None:
            from metrics.metrics_collector import MetricsCollector
            self.metrics_collector = MetricsCollector()
        
        # Document index mappings
        self.document_index_map = {}
        self.document_index_map_path = os.path.join(
            ARISConfig.VECTORSTORE_PATH,
            "document_index_map.json"
        )
        self._load_document_index_map()

    def _load_document_index_map(self):
        import json
        if os.path.exists(self.document_index_map_path):
            try:
                with open(self.document_index_map_path, 'r') as f:
                    self.document_index_map = json.load(f)
                    logger.info(f"Loaded {len(self.document_index_map)} document-index mappings")
            except Exception as e:
                logger.warning(f"Could not load document index map: {e}")
    
    def _save_document_index_map(self):
        import json
        os.makedirs(os.path.dirname(self.document_index_map_path), exist_ok=True)
        try:
            with open(self.document_index_map_path, 'w') as f:
                json.dump(self.document_index_map, f, indent=2)
            logger.info(f"Saved {len(self.document_index_map)} document-index mappings")
        except Exception as e:
            logger.error(f"Could not save document index map: {e}")

    def process_documents(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None, index_name: Optional[str] = None):
        documents = []
        for text in texts:
            documents.append({
                'content': text,
                'metadata': metadatas if metadatas else {}
            })
        
        if self.vectorstore:
            self.vectorstore.add_documents(documents)

    def add_documents_incremental(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None, index_name: Optional[str] = None) -> Dict:
        if not texts:
            return 0
        return self.process_documents(texts, metadatas, progress_callback, index_name)

    def check_index_exists(self, index_name: str) -> bool:
        if self.vector_store_type == 'opensearch':
            from vectorstores.opensearch_store import OpenSearchVectorStore
            temp_store = OpenSearchVectorStore(
                embeddings=self.embeddings,
                domain=self.opensearch_domain,
                index_name=index_name
            )
            return temp_store.index_exists(index_name)
        elif self.vector_store_type == 'pgvector':
            from vectorstores.pgvector_store import PgVectorStore
            temp_store = PgVectorStore(
                embeddings=self.embeddings,
                domain=self.pgvector_domain,
                index_name=index_name
            )
            return temp_store.index_exists(index_name)

    def get_next_index_name(self, base_name: str) -> str:
        if self.vector_store_type == 'opensearch':
            from vectorstores.opensearch_store import OpenSearchVectorStore
            temp_store = OpenSearchVectorStore(
                embeddings=self.embeddings,
                domain=self.opensearch_domain,
                index_name=base_name
            )
            return temp_store.get_next_index_name(base_name)
        elif self.vector_store_type == 'pgvector':
            from vectorstores.pgvector_store import PgVectorStore
            temp_store = PgVectorStore(
                embeddings=self.embeddings,
                domain=self.pgvector_domain,
                index_name=base_name
            )
            return temp_store.get_next_index_name(base_name)
