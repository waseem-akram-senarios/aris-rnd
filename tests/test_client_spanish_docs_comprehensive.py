"""
Comprehensive R&D Test Suite for Client Spanish Documents
Tests all documents in docs/testing/clientSpanishDocs with:
- Multiple parsers (Docling, PyMuPDF, OCRmyPDF)
- Cross-language queries (Spanish docs with English queries, etc.)
- Multiple parameter combinations
- Server-based testing
- Detailed accuracy metrics and recommendations
"""

import os
import sys
import time
import json
import requests
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import statistics
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

BASE_URL = "http://44.221.84.58:8500"
DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'testing', 'clientSpanishDocs')

@dataclass
class TestConfig:
    """Test configuration"""
    parser: str
    search_mode: str
    semantic_weight: float
    k: int
    auto_translate: bool
    temperature: float
    response_language: Optional[str] = None
    use_agentic_rag: bool = False

@dataclass
class TestResult:
    """Test result"""
    config: TestConfig
    query: str
    query_language: str
    document_name: str
    document_id: str
    parser: str
    citations_count: int
    avg_similarity: float
    max_similarity: float
    min_similarity: float
    response_time: float
    answer_length: int
    answer_quality_score: float
    answer: str
    error: Optional[str] = None
    has_contact_info: bool = False
    has_email: bool = False
    has_phone: bool = False

class ClientSpanishDocsTester:
    """Comprehensive tester for client Spanish documents"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.uploaded_docs: Dict[str, Dict] = {}
        
    def check_server_health(self) -> bool:
        """Check if server is accessible"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_documents(self) -> List[Dict]:
        """Get all documents from server"""
        try:
            response = requests.get(f"{self.base_url}/documents", timeout=30)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "documents" in data:
                return data["documents"]
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"⚠️  Error getting documents: {e}")
            return []
    
    def upload_document(self, file_path: str, parser: str, language: str = "spa") -> Dict:
        """Upload document with specific parser"""
        url = f"{self.base_url}/documents"
        
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            data = {
                'parser_preference': parser,
                'language': language
            }
            
            try:
                print(f"      📤 Uploading {os.path.basename(file_path)} with {parser}...")
                response = requests.post(url, files=files, data=data, timeout=600)
                response.raise_for_status()
                result = response.json()
                print(f"      ✅ Uploaded: {result.get('document_id', 'unknown')} ({result.get('chunks_created', 0)} chunks)")
                return result
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_msg = e.response.json().get('detail', error_msg)
                    except:
                        error_msg = e.response.text[:200]
                print(f"      ❌ Error: {error_msg}")
                return {"error": error_msg}
    
    def query_with_config(self, question: str, document_id: str, config: TestConfig, response_language: Optional[str] = None) -> Dict:
        """Query with specific configuration"""
        url = f"{self.base_url}/query"
        
        payload = {
            "question": question,
            "k": config.k,
            "search_mode": config.search_mode,
            "use_hybrid_search": (config.search_mode == "hybrid"),
            "semantic_weight": config.semantic_weight,
            "auto_translate": config.auto_translate,
            "temperature": config.temperature,
            "document_id": document_id,
            "active_sources": [document_id],
            "use_agentic_rag": config.use_agentic_rag
        }
        
        # Set response language
        if response_language:
            payload["response_language"] = response_language
        elif config.response_language:
            payload["response_language"] = config.response_language
        
        try:
            start_time = time.time()
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            result['response_time'] = time.time() - start_time
            return result
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_msg = e.response.json().get('detail', error_msg)
                except:
                    error_msg = e.response.text[:200]
            return {"error": error_msg, "answer": "", "citations": [], "response_time": 0}
    
    def evaluate_answer_quality(self, answer: str, query: str, expected_keywords: List[str] = None) -> Tuple[float, Dict]:
        """Evaluate answer quality (0-100) and extract metadata"""
        metadata = {
            "has_contact_info": False,
            "has_email": False,
            "has_phone": False
        }
        
        if not answer or len(answer.strip()) < 20:
            return 0.0, metadata
        
        answer_lower = answer.lower()
        
        # Check for error indicators
        error_phrases = [
            "i don't know", "i cannot", "no information", "not found",
            "check the manual", "no se encuentra", "no disponible",
            "no puedo", "no tengo", "no hay información"
        ]
        
        for phrase in error_phrases:
            if phrase in answer_lower:
                return 20.0, metadata
        
        # Check for contact information
        email_patterns = ["@", "email", "correo", "e-mail"]
        phone_patterns = ["phone", "teléfono", "tel:", "telefono", "+", "(", ")"]
        
        if any(pattern in answer_lower for pattern in email_patterns):
            metadata["has_email"] = True
            metadata["has_contact_info"] = True
        
        if any(pattern in answer_lower for pattern in phone_patterns):
            metadata["has_phone"] = True
            metadata["has_contact_info"] = True
        
        # Base score for valid answer
        score = 50.0
        
        # Keyword matching
        if expected_keywords:
            found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
            score += (found / len(expected_keywords)) * 30
        
        # Length and detail score
        if len(answer) > 100:
            score += 10
        if len(answer) > 200:
            score += 10
        if len(answer) > 500:
            score += 5
        
        # Contact info bonus
        if metadata["has_contact_info"]:
            score += 10
        
        return min(100.0, score), metadata
    
    def run_comprehensive_test(self) -> Dict:
        """Run comprehensive test suite"""
        print("=" * 100)
        print("🔬 COMPREHENSIVE R&D TEST - CLIENT SPANISH DOCUMENTS")
        print("=" * 100)
        print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Server: {self.base_url}")
        print(f"📁 Documents Directory: {DOCS_DIR}")
        print()
        
        # Check server health
        if not self.check_server_health():
            print("❌ Server is not accessible. Please check the server URL.")
            return {"error": "Server not accessible"}
        
        print("✅ Server is accessible")
        
        # Find PDF files
        pdf_files = []
        if os.path.exists(DOCS_DIR):
            for file in os.listdir(DOCS_DIR):
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(DOCS_DIR, file))
        
        if not pdf_files:
            print(f"❌ No PDF files found in {DOCS_DIR}")
            return {"error": "No PDF files found"}
        
        print(f"\n📚 Found {len(pdf_files)} PDF file(s):")
        for pdf in pdf_files:
            print(f"   - {os.path.basename(pdf)}")
        
        # Test configurations - Comprehensive parameter grid
        # NOTE: k values are limited to max 20 per QueryRequest schema validation
        test_configs = [
            # Baseline configurations
            TestConfig("pymupdf", "hybrid", 0.4, 20, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None, False),  # Cross-language optimized
            TestConfig("pymupdf", "hybrid", 0.6, 20, True, 0.1, None, False),
            
            # Different k values for cross-language (max 20 per schema)
            TestConfig("pymupdf", "hybrid", 0.2, 10, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.2, 15, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None, False),
            
            # Different semantic weights
            TestConfig("pymupdf", "hybrid", 0.1, 20, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.3, 20, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.4, 20, True, 0.1, None, False),
            
            # Different search modes
            TestConfig("pymupdf", "semantic", 1.0, 20, True, 0.1, None, False),
            TestConfig("pymupdf", "keyword", 0.0, 20, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None, False),
            
            # Auto-translate variations
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None, False),
            TestConfig("pymupdf", "hybrid", 0.2, 20, False, 0.1, None, False),
            
            # Response language variations
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, "Auto", False),
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, "Spanish", False),
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, "English", False),
            
            # Agentic RAG
            TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None, True),
            
            # Different parsers with best params
            TestConfig("docling", "hybrid", 0.2, 20, True, 0.1, None, False),
            TestConfig("ocrmypdf", "hybrid", 0.2, 20, True, 0.1, None, False),
        ]
        
        # Comprehensive test queries - Cross-language focused
        test_queries = [
            {
                "spanish": "¿Dónde está el email y contacto de Vuormar?",
                "english": "Where is the email and contact of Vuormar?",
                "keywords": ["email", "correo", "contact", "contacto", "phone", "teléfono", "vuormar"],
                "type": "contact_info"
            },
            {
                "spanish": "¿Cuál es el correo electrónico de Vuormar?",
                "english": "What is the email address of Vuormar?",
                "keywords": ["email", "correo", "electrónico", "vuormar"],
                "type": "contact_info"
            },
            {
                "spanish": "¿Cómo aumentar o disminuir los niveles de aire en la bolsa?",
                "english": "How to increase or decrease the levels of air in bag?",
                "keywords": ["aire", "air", "bolsa", "bag", "aumentar", "increase", "disminuir", "decrease"],
                "type": "procedure"
            },
            {
                "spanish": "¿Cuál es el procedimiento de mantenimiento?",
                "english": "What is the maintenance procedure?",
                "keywords": ["mantenimiento", "maintenance", "procedimiento", "procedure"],
                "type": "procedure"
            },
            {
                "spanish": "¿Qué es el degasado?",
                "english": "What is degassing?",
                "keywords": ["degasado", "degassing", "degas", "aire"],
                "type": "definition"
            },
            {
                "spanish": "¿Cómo funciona el sello superior?",
                "english": "How does the top seal work?",
                "keywords": ["sello", "seal", "superior", "top", "funciona", "work"],
                "type": "definition"
            },
            {
                "spanish": "¿Cuáles son las especificaciones técnicas?",
                "english": "What are the technical specifications?",
                "keywords": ["especificaciones", "specifications", "técnicas", "technical"],
                "type": "specifications"
            },
        ]
        
        # Upload documents with different parsers
        print("\n" + "=" * 100)
        print("📤 UPLOADING DOCUMENTS")
        print("=" * 100)
        
        parsers = ["pymupdf", "docling", "ocrmypdf"]
        
        for pdf_path in pdf_files:
            doc_name = os.path.basename(pdf_path)
            print(f"\n📄 Processing: {doc_name}")
            
            for parser in parsers:
                result = self.upload_document(pdf_path, parser, language="spa")
                
                if "error" in result:
                    continue
                
                doc_id = result.get('document_id')
                if doc_id:
                    key = f"{doc_name}_{parser}"
                    chunks = result.get('chunks_created', 0)
                    
                    # Wait for processing if chunks are 0
                    if chunks == 0:
                        print(f"      ⏳ Document processing... waiting up to 60 seconds")
                        max_wait = 60
                        waited = 0
                        while waited < max_wait:
                            time.sleep(5)
                            waited += 5
                            # Check document status
                            try:
                                doc_check = requests.get(f"{self.base_url}/documents/{doc_id}", timeout=10)
                                if doc_check.status_code == 200:
                                    doc_data = doc_check.json()
                                    chunks = doc_data.get('chunks_created', 0)
                                    if chunks > 0:
                                        print(f"      ✅ Processing complete: {chunks} chunks")
                                        break
                                    print(f"      ⏳ Still processing... ({waited}s)")
                            except:
                                pass
                    
                    self.uploaded_docs[key] = {
                        'document_id': doc_id,
                        'document_name': doc_name,
                        'parser': parser,
                        'chunks': chunks,
                        'file_path': pdf_path
                    }
                
                time.sleep(3)  # Rate limiting
        
        # Also check for existing documents on server
        print("\n🔍 Checking for existing documents on server...")
        existing_docs = self.get_documents()
        for doc in existing_docs:
            if isinstance(doc, dict):
                doc_name = doc.get('document_name', '').lower()
                doc_id = doc.get('document_id')
                parser = doc.get('parser_used', 'unknown')
                chunks = doc.get('chunks_created', 0)
                
                # Check if it matches our test documents
                for pdf_file in pdf_files:
                    pdf_name = os.path.basename(pdf_file).lower()
                    if pdf_name in doc_name or any(part in doc_name for part in ['vuormar', 'em10', 'em11', 'degasing', 'top seal']):
                        key = f"{os.path.basename(pdf_file)}_{parser}"
                        if key not in self.uploaded_docs and chunks > 0:
                            print(f"   ✅ Found existing: {doc.get('document_name')} ({parser}, {chunks} chunks)")
                            self.uploaded_docs[key] = {
                                'document_id': doc_id,
                                'document_name': doc.get('document_name'),
                                'parser': parser,
                                'chunks': chunks,
                                'file_path': pdf_file
                            }
        
        if not self.uploaded_docs:
            print("❌ No documents available for testing")
            return {"error": "No documents available"}
        
        # Filter out documents with 0 chunks
        valid_docs = {k: v for k, v in self.uploaded_docs.items() if v.get('chunks', 0) > 0}
        if valid_docs:
            print(f"\n✅ Found {len(valid_docs)} document variants with chunks ready for testing")
            self.uploaded_docs = valid_docs
        else:
            print(f"\n⚠️  Warning: No documents with chunks found. Proceeding with {len(self.uploaded_docs)} documents anyway...")
        
        if not self.uploaded_docs:
            print("❌ No documents available for testing")
            return {"error": "No documents available"}
        
        # Run comprehensive tests
        print("\n" + "=" * 100)
        print("🧪 RUNNING COMPREHENSIVE TESTS")
        print("=" * 100)
        
        total_tests = len(self.uploaded_docs) * len(test_configs) * len(test_queries) * 2  # Spanish + English
        test_count = 0
        
        for doc_key, doc_info in self.uploaded_docs.items():
            doc_id = doc_info['document_id']
            doc_name = doc_info['document_name']
            parser = doc_info['parser']
            
            print(f"\n{'='*100}")
            print(f"📄 Testing: {doc_name} (Parser: {parser})")
            print(f"{'='*100}")
            
            # Filter configs for this parser
            relevant_configs = [c for c in test_configs if c.parser == parser]
            if not relevant_configs:
                relevant_configs = [c for c in test_configs if c.parser == "pymupdf"]
            
            for config_idx, config in enumerate(relevant_configs, 1):
                print(f"\n⚙️  Config {config_idx}/{len(relevant_configs)}: {config.search_mode}, k={config.k}, sw={config.semantic_weight:.2f}, at={config.auto_translate}, temp={config.temperature}")
                
                for query_set in test_queries:
                    # Test both Spanish and English queries
                    for lang, query in [("spanish", query_set["spanish"]), ("english", query_set["english"])]:
                        test_count += 1
                        print(f"\n   [{test_count}/{total_tests}] 🔍 Query ({lang}): {query[:60]}...")
                        
                        # Determine response language
                        response_lang = None
                        if config.response_language:
                            if config.response_language == "Auto":
                                response_lang = None  # Will be auto-detected
                            else:
                                response_lang = config.response_language
                        elif lang == "spanish":
                            response_lang = "Spanish"
                        else:
                            response_lang = "English"
                        
                        result = self.query_with_config(query, doc_id, config, response_lang)
                        
                        if "error" in result:
                            print(f"      ❌ Error: {result['error']}")
                            test_result = TestResult(
                                config=config,
                                query=query,
                                query_language=lang,
                                document_name=doc_name,
                                document_id=doc_id,
                                parser=parser,
                                citations_count=0,
                                avg_similarity=0.0,
                                max_similarity=0.0,
                                min_similarity=0.0,
                                response_time=0.0,
                                answer_length=0,
                                answer_quality_score=0.0,
                                answer="",
                                error=result['error']
                            )
                            self.results.append(test_result)
                            continue
                        
                        citations = result.get('citations', [])
                        similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                        avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
                        max_sim = max(similarities) if similarities else 0.0
                        min_sim = min(similarities) if similarities else 0.0
                        
                        answer = result.get('answer', '')
                        quality, metadata = self.evaluate_answer_quality(answer, query, query_set.get('keywords', []))
                        
                        test_result = TestResult(
                            config=config,
                            query=query,
                            query_language=lang,
                            document_name=doc_name,
                            document_id=doc_id,
                            parser=parser,
                            citations_count=len(citations),
                            avg_similarity=avg_sim,
                            max_similarity=max_sim,
                            min_similarity=min_sim,
                            response_time=result.get('response_time', 0),
                            answer_length=len(answer),
                            answer_quality_score=quality,
                            answer=answer[:200] + "..." if len(answer) > 200 else answer,
                            has_contact_info=metadata["has_contact_info"],
                            has_email=metadata["has_email"],
                            has_phone=metadata["has_phone"]
                        )
                        
                        self.results.append(test_result)
                        
                        print(f"      📊 Citations: {len(citations)}, Sim: {min_sim:.1f}%-{max_sim:.1f}% (avg: {avg_sim:.1f}%), Quality: {quality:.1f}%, Time: {result.get('response_time', 0):.2f}s")
                        if metadata["has_contact_info"]:
                            print(f"      ✅ Contact info detected")
                        
                        time.sleep(1)  # Rate limiting
        
        # Analyze results
        return self.analyze_results()
    
    def analyze_results(self) -> Dict:
        """Analyze test results and provide recommendations"""
        if not self.results:
            return {"error": "No results to analyze"}
        
        print("\n" + "=" * 100)
        print("📊 COMPREHENSIVE ANALYSIS & RECOMMENDATIONS")
        print("=" * 100)
        
        # Filter out errors
        valid_results = [r for r in self.results if not r.error]
        
        if not valid_results:
            print("❌ No valid results to analyze")
            return {"error": "No valid results"}
        
        print(f"\n✅ Analyzing {len(valid_results)} valid test results")
        
        # Group by different dimensions
        by_parser = {}
        by_query_language = {}
        by_search_mode = {}
        by_semantic_weight = {}
        by_k = {}
        by_auto_translate = {}
        by_response_language = {}
        by_agentic = {}
        
        for result in valid_results:
            # By parser
            parser = result.parser
            if parser not in by_parser:
                by_parser[parser] = []
            by_parser[parser].append(result)
            
            # By query language
            qlang = result.query_language
            if qlang not in by_query_language:
                by_query_language[qlang] = []
            by_query_language[qlang].append(result)
            
            # By search mode
            mode = result.config.search_mode
            if mode not in by_search_mode:
                by_search_mode[mode] = []
            by_search_mode[mode].append(result)
            
            # By semantic weight
            sw = result.config.semantic_weight
            sw_key = f"{sw:.2f}"
            if sw_key not in by_semantic_weight:
                by_semantic_weight[sw_key] = []
            by_semantic_weight[sw_key].append(result)
            
            # By k
            k = result.config.k
            if k not in by_k:
                by_k[k] = []
            by_k[k].append(result)
            
            # By auto_translate
            at = result.config.auto_translate
            at_key = "enabled" if at else "disabled"
            if at_key not in by_auto_translate:
                by_auto_translate[at_key] = []
            by_auto_translate[at_key].append(result)
            
            # By response language
            rlang = result.config.response_language or "None"
            if rlang not in by_response_language:
                by_response_language[rlang] = []
            by_response_language[rlang].append(result)
            
            # By agentic
            agentic = result.config.use_agentic_rag
            agentic_key = "enabled" if agentic else "disabled"
            if agentic_key not in by_agentic:
                by_agentic[agentic_key] = []
            by_agentic[agentic_key].append(result)
        
        # Calculate statistics
        def calc_stats(results: List[TestResult]) -> Dict:
            if not results:
                return {}
            return {
                "count": len(results),
                "avg_quality": statistics.mean([r.answer_quality_score for r in results]),
                "median_quality": statistics.median([r.answer_quality_score for r in results]),
                "avg_similarity": statistics.mean([r.avg_similarity for r in results]),
                "avg_citations": statistics.mean([r.citations_count for r in results]),
                "avg_response_time": statistics.mean([r.response_time for r in results]),
                "contact_info_rate": sum(1 for r in results if r.has_contact_info) / len(results) * 100
            }
        
        # Print analysis
        print("\n" + "-" * 100)
        print("📈 PERFORMANCE BY PARSER")
        print("-" * 100)
        for parser, results in sorted(by_parser.items(), key=lambda x: calc_stats(x[1]).get("avg_quality", 0), reverse=True):
            stats = calc_stats(results)
            print(f"\n{parser.upper()}:")
            print(f"  Tests: {stats['count']}")
            print(f"  Avg Quality: {stats['avg_quality']:.2f}%")
            print(f"  Median Quality: {stats['median_quality']:.2f}%")
            print(f"  Avg Similarity: {stats['avg_similarity']:.2f}%")
            print(f"  Avg Citations: {stats['avg_citations']:.1f}")
            print(f"  Contact Info Rate: {stats['contact_info_rate']:.1f}%")
            print(f"  Avg Response Time: {stats['avg_response_time']:.2f}s")
        
        print("\n" + "-" * 100)
        print("🌐 PERFORMANCE BY QUERY LANGUAGE")
        print("-" * 100)
        for qlang, results in sorted(by_query_language.items(), key=lambda x: calc_stats(x[1]).get("avg_quality", 0), reverse=True):
            stats = calc_stats(results)
            print(f"\n{qlang.upper()}:")
            print(f"  Tests: {stats['count']}")
            print(f"  Avg Quality: {stats['avg_quality']:.2f}%")
            print(f"  Avg Similarity: {stats['avg_similarity']:.2f}%")
            print(f"  Contact Info Rate: {stats['contact_info_rate']:.1f}%")
        
        print("\n" + "-" * 100)
        print("🔍 PERFORMANCE BY SEARCH MODE")
        print("-" * 100)
        for mode, results in sorted(by_search_mode.items(), key=lambda x: calc_stats(x[1]).get("avg_quality", 0), reverse=True):
            stats = calc_stats(results)
            print(f"\n{mode.upper()}:")
            print(f"  Tests: {stats['count']}")
            print(f"  Avg Quality: {stats['avg_quality']:.2f}%")
            print(f"  Avg Similarity: {stats['avg_similarity']:.2f}%")
        
        print("\n" + "-" * 100)
        print("⚖️  PERFORMANCE BY SEMANTIC WEIGHT")
        print("-" * 100)
        for sw, results in sorted(by_semantic_weight.items(), key=lambda x: float(x[0]), reverse=True):
            stats = calc_stats(results)
            print(f"\nSemantic Weight {sw}:")
            print(f"  Tests: {stats['count']}")
            print(f"  Avg Quality: {stats['avg_quality']:.2f}%")
            print(f"  Avg Similarity: {stats['avg_similarity']:.2f}%")
        
        print("\n" + "-" * 100)
        print("📊 PERFORMANCE BY K (Number of Chunks)")
        print("-" * 100)
        for k, results in sorted(by_k.items(), key=lambda x: x[0]):
            stats = calc_stats(results)
            print(f"\nK={k}:")
            print(f"  Tests: {stats['count']}")
            print(f"  Avg Quality: {stats['avg_quality']:.2f}%")
            print(f"  Avg Citations: {stats['avg_citations']:.1f}")
        
        print("\n" + "-" * 100)
        print("🔄 PERFORMANCE BY AUTO-TRANSLATE")
        print("-" * 100)
        for at, results in sorted(by_auto_translate.items()):
            stats = calc_stats(results)
            print(f"\nAuto-Translate {at.upper()}:")
            print(f"  Tests: {stats['count']}")
            print(f"  Avg Quality: {stats['avg_quality']:.2f}%")
            print(f"  Avg Similarity: {stats['avg_similarity']:.2f}%")
        
        # Find best configuration
        print("\n" + "=" * 100)
        print("🏆 BEST CONFIGURATIONS")
        print("=" * 100)
        
        # Group by configuration
        config_scores = {}
        for result in valid_results:
            config_key = (
                result.parser,
                result.config.search_mode,
                result.config.semantic_weight,
                result.config.k,
                result.config.auto_translate,
                result.config.response_language or "None",
                result.config.use_agentic_rag
            )
            if config_key not in config_scores:
                config_scores[config_key] = []
            config_scores[config_key].append(result.answer_quality_score)
        
        # Sort by average quality
        best_configs = sorted(
            config_scores.items(),
            key=lambda x: statistics.mean(x[1]),
            reverse=True
        )[:10]
        
        print("\nTop 10 Configurations (by average quality score):")
        for idx, (config, scores) in enumerate(best_configs, 1):
            parser, mode, sw, k, at, rlang, agentic = config
            avg_score = statistics.mean(scores)
            print(f"\n{idx}. Parser: {parser}, Mode: {mode}, SW: {sw:.2f}, K: {k}, AT: {at}, RLang: {rlang}, Agentic: {agentic}")
            print(f"   Avg Quality: {avg_score:.2f}% (from {len(scores)} tests)")
        
        # Cross-language specific analysis
        print("\n" + "=" * 100)
        print("🌍 CROSS-LANGUAGE ANALYSIS")
        print("=" * 100)
        
        cross_lang_results = [r for r in valid_results if r.query_language == "english"]
        same_lang_results = [r for r in valid_results if r.query_language == "spanish"]
        
        if cross_lang_results:
            cross_stats = calc_stats(cross_lang_results)
            print(f"\nCross-Language (English queries on Spanish docs):")
            print(f"  Tests: {cross_stats['count']}")
            print(f"  Avg Quality: {cross_stats['avg_quality']:.2f}%")
            print(f"  Avg Similarity: {cross_stats['avg_similarity']:.2f}%")
            print(f"  Contact Info Rate: {cross_stats['contact_info_rate']:.1f}%")
        
        if same_lang_results:
            same_stats = calc_stats(same_lang_results)
            print(f"\nSame-Language (Spanish queries on Spanish docs):")
            print(f"  Tests: {same_stats['count']}")
            print(f"  Avg Quality: {same_stats['avg_quality']:.2f}%")
            print(f"  Avg Similarity: {same_stats['avg_similarity']:.2f}%")
            print(f"  Contact Info Rate: {same_stats['contact_info_rate']:.1f}%")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"tests/client_spanish_docs_test_results_{timestamp}.json"
        
        results_data = {
            "timestamp": timestamp,
            "server_url": self.base_url,
            "total_tests": len(self.results),
            "valid_tests": len(valid_results),
            "uploaded_documents": {k: {**v, 'file_path': str(v['file_path'])} for k, v in self.uploaded_docs.items()},
            "results": [asdict(r) for r in self.results],
            "analysis": {
                "by_parser": {k: calc_stats(v) for k, v in by_parser.items()},
                "by_query_language": {k: calc_stats(v) for k, v in by_query_language.items()},
                "by_search_mode": {k: calc_stats(v) for k, v in by_search_mode.items()},
                "by_semantic_weight": {k: calc_stats(v) for k, v in by_semantic_weight.items()},
                "by_k": {k: calc_stats(v) for k, v in by_k.items()},
                "by_auto_translate": {k: calc_stats(v) for k, v in by_auto_translate.items()},
                "best_configurations": [
                    {
                        "parser": config[0],
                        "search_mode": config[1],
                        "semantic_weight": config[2],
                        "k": config[3],
                        "auto_translate": config[4],
                        "response_language": config[5],
                        "use_agentic_rag": config[6],
                        "avg_quality": statistics.mean(scores),
                        "test_count": len(scores)
                    }
                    for config, scores in best_configs
                ]
            }
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {results_file}")
        
        return results_data

def main():
    """Main test execution"""
    tester = ClientSpanishDocsTester()
    results = tester.run_comprehensive_test()
    
    if "error" in results:
        print(f"\n❌ Test failed: {results['error']}")
        sys.exit(1)
    
    print("\n" + "=" * 100)
    print("✅ COMPREHENSIVE TEST COMPLETE")
    print("=" * 100)

if __name__ == "__main__":
    main()

