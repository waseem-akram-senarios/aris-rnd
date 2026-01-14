"""
Comprehensive System-Wide Parameter Optimization
Tests ingestion AND retrieval parameters to find optimal configuration
"""

import os
import sys
import time
import json
import requests
import statistics
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

BASE_URL = "http://44.221.84.58:8500"

@dataclass
class IngestionConfig:
    """Ingestion parameters"""
    parser: str
    chunk_size: int
    chunk_overlap: int

@dataclass
class RetrievalConfig:
    """Retrieval parameters"""
    search_mode: str
    semantic_weight: float
    k: int
    use_mmr: bool
    auto_translate: bool
    temperature: float
    use_agentic_rag: bool

@dataclass
class TestResult:
    """Test result"""
    ingestion: IngestionConfig
    retrieval: RetrievalConfig
    query: str
    query_language: str
    document_name: str
    # Ingestion metrics
    chunks_created: int
    ingestion_time: float
    # Retrieval metrics
    citations_count: int
    avg_similarity: float
    max_similarity: float
    response_time: float
    answer_quality: float
    answer_length: int
    has_relevant_info: bool
    error: str = None

class SystemOptimizer:
    """Comprehensive system optimizer"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[TestResult] = []
        
    def upload_document(self, file_path: str, parser: str, chunk_size: int = None, chunk_overlap: int = None) -> Dict:
        """Upload document with specific ingestion parameters"""
        url = f"{self.base_url}/documents"
        
        data = {'parser_preference': parser}
        if chunk_size:
            data['chunk_size'] = str(chunk_size)
        if chunk_overlap:
            data['chunk_overlap'] = str(chunk_overlap)
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            
            try:
                start_time = time.time()
                response = requests.post(url, files=files, data=data, timeout=300)
                response.raise_for_status()
                result = response.json()
                result['ingestion_time'] = time.time() - start_time
                return result
            except Exception as e:
                return {"error": str(e), "ingestion_time": 0}
    
    def query_with_config(self, question: str, document_id: str, config: RetrievalConfig) -> Dict:
        """Query with specific retrieval configuration"""
        url = f"{self.base_url}/query"
        
        payload = {
            "question": question,
            "k": config.k,
            "search_mode": config.search_mode,
            "use_hybrid_search": (config.search_mode == "hybrid"),
            "semantic_weight": config.semantic_weight,
            "use_mmr": config.use_mmr,
            "auto_translate": config.auto_translate,
            "temperature": config.temperature,
            "use_agentic_rag": config.use_agentic_rag,
            "document_id": document_id,
            "active_sources": [document_id]
        }
        
        try:
            start_time = time.time()
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            result['response_time'] = time.time() - start_time
            return result
        except Exception as e:
            return {"error": str(e), "answer": "", "citations": [], "response_time": 0}
    
    def evaluate_answer(self, answer: str, query: str, expected_keywords: List[str] = None) -> Tuple[float, bool]:
        """Evaluate answer quality and relevance"""
        if not answer or len(answer.strip()) < 20:
            return 0.0, False
        
        # Check for error indicators
        error_phrases = [
            "i don't know", "i cannot", "no information", "not found",
            "check the manual", "no se encuentra", "no disponible", "not mentioned",
            "doesn't contain", "does not contain", "no incluye"
        ]
        
        answer_lower = answer.lower()
        has_error = any(phrase in answer_lower for phrase in error_phrases)
        
        if has_error:
            return 25.0, False
        
        # Base score for non-error response
        score = 50.0
        
        # Check for expected keywords
        if expected_keywords:
            found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
            keyword_score = (found / len(expected_keywords)) * 35
            score += keyword_score
            has_relevant = found >= len(expected_keywords) * 0.5
        else:
            has_relevant = True
        
        # Length and detail bonus
        if len(answer) > 100:
            score += 8
        if len(answer) > 200:
            score += 7
        
        return min(100.0, score), has_relevant
    
    def run_comprehensive_test(self, docs_dir: str) -> Dict:
        """Run comprehensive system-wide optimization"""
        print("=" * 80)
        print("🔬 COMPREHENSIVE SYSTEM OPTIMIZATION")
        print("=" * 80)
        
        # Ingestion configurations to test
        ingestion_configs = [
            # Chunk size variations
            IngestionConfig("pymupdf", 512, 128),   # Current default
            IngestionConfig("pymupdf", 384, 96),    # Smaller chunks
            IngestionConfig("pymupdf", 768, 192),   # Larger chunks
            IngestionConfig("pymupdf", 1024, 256),  # Very large chunks
            
            # Overlap variations (with 512 chunk size)
            IngestionConfig("pymupdf", 512, 64),    # Less overlap
            IngestionConfig("pymupdf", 512, 128),   # Default overlap
            IngestionConfig("pymupdf", 512, 192),   # More overlap
            
            # Parser variations (with best chunk config)
            IngestionConfig("pymupdf", 512, 128),
            IngestionConfig("docling", 512, 128),
            IngestionConfig("ocrmypdf", 512, 128),
        ]
        
        # Retrieval configurations to test
        retrieval_configs = [
            # Semantic weight variations
            RetrievalConfig("hybrid", 0.3, 20, False, True, 0.2, False),
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.2, False),  # Current best
            RetrievalConfig("hybrid", 0.5, 20, False, True, 0.2, False),
            RetrievalConfig("hybrid", 0.6, 20, False, True, 0.2, False),
            
            # K variations (with best semantic weight)
            RetrievalConfig("hybrid", 0.4, 15, False, True, 0.2, False),
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.2, False),  # Current best
            RetrievalConfig("hybrid", 0.4, 25, False, True, 0.2, False),
            RetrievalConfig("hybrid", 0.4, 30, False, True, 0.2, False),
            
            # MMR variations
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.2, False),  # No MMR
            RetrievalConfig("hybrid", 0.4, 20, True, True, 0.2, False),   # With MMR
            
            # Temperature variations
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.0, False),
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.2, False),  # Current
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.5, False),
            
            # Agentic RAG variations
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.2, False),  # No agentic
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.2, True),   # With agentic
            
            # Search mode variations
            RetrievalConfig("semantic", 1.0, 20, False, True, 0.2, False),
            RetrievalConfig("keyword", 0.0, 20, False, True, 0.2, False),
            RetrievalConfig("hybrid", 0.4, 20, False, True, 0.2, False),
        ]
        
        # Test queries
        test_queries = [
            {
                "spanish": "¿Dónde está el email y contacto de Vuormar?",
                "english": "Where is the email and contact of Vuormar?",
                "keywords": ["email", "correo", "contact", "contacto", "phone", "teléfono", "mattia", "stellini"]
            },
            {
                "spanish": "¿Cómo aumentar o disminuir los niveles de aire?",
                "english": "How to increase or decrease the air levels?",
                "keywords": ["aire", "air", "aumentar", "increase", "disminuir", "decrease", "nivel"]
            },
            {
                "spanish": "¿Cuál es el procedimiento de mantenimiento?",
                "english": "What is the maintenance procedure?",
                "keywords": ["mantenimiento", "maintenance", "procedimiento", "procedure", "pasos", "steps"]
            }
        ]
        
        # Find test documents
        pdf_files = []
        if os.path.exists(docs_dir):
            for file in os.listdir(docs_dir):
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(docs_dir, file))
        
        if not pdf_files:
            print(f"❌ No PDF files found in {docs_dir}")
            # Fall back to existing documents
            return self.test_existing_documents(retrieval_configs, test_queries)
        
        print(f"\n📚 Found {len(pdf_files)} PDF file(s)")
        for pdf in pdf_files:
            print(f"   - {os.path.basename(pdf)}")
        
        # Test each ingestion configuration
        print("\n" + "=" * 80)
        print("🔧 PHASE 1: INGESTION OPTIMIZATION")
        print("=" * 80)
        
        uploaded_docs = []
        
        for i, ing_config in enumerate(ingestion_configs[:6], 1):  # Test first 6 configs
            for pdf_path in pdf_files[:1]:  # Test with first document
                doc_name = os.path.basename(pdf_path)
                
                print(f"\n[{i}/{min(6, len(ingestion_configs))}] Testing ingestion:")
                print(f"   Document: {doc_name}")
                print(f"   Parser: {ing_config.parser}")
                print(f"   Chunk Size: {ing_config.chunk_size}")
                print(f"   Chunk Overlap: {ing_config.chunk_overlap}")
                
                result = self.upload_document(
                    pdf_path, 
                    ing_config.parser,
                    ing_config.chunk_size,
                    ing_config.chunk_overlap
                )
                
                if "error" in result:
                    print(f"   ❌ Error: {result['error']}")
                    continue
                
                doc_id = result.get('document_id')
                chunks = result.get('chunks_created', 0)
                ing_time = result.get('ingestion_time', 0)
                
                print(f"   ✅ Uploaded: {chunks} chunks in {ing_time:.1f}s")
                
                if doc_id:
                    uploaded_docs.append({
                        'document_id': doc_id,
                        'document_name': doc_name,
                        'ingestion_config': ing_config,
                        'chunks': chunks,
                        'ingestion_time': ing_time
                    })
                
                time.sleep(3)  # Rate limiting
        
        if not uploaded_docs:
            print("❌ No documents uploaded. Using existing documents.")
            return self.test_existing_documents(retrieval_configs, test_queries)
        
        print(f"\n✅ Successfully uploaded {len(uploaded_docs)} document variant(s)")
        
        # Test retrieval on each uploaded document
        print("\n" + "=" * 80)
        print("🔍 PHASE 2: RETRIEVAL OPTIMIZATION")
        print("=" * 80)
        
        test_count = 0
        
        for doc_info in uploaded_docs:
            doc_id = doc_info['document_id']
            doc_name = doc_info['document_name']
            ing_config = doc_info['ingestion_config']
            
            print(f"\n📄 Testing retrieval on: {doc_name}")
            print(f"   Ingestion: {ing_config.parser}, {ing_config.chunk_size}/{ing_config.chunk_overlap}")
            print("-" * 80)
            
            for ret_config in retrieval_configs[:10]:  # Test first 10 retrieval configs
                for query_set in test_queries[:2]:  # Test first 2 query types
                    for lang, query in [("Spanish", query_set["spanish"]), ("English", query_set["english"])]:
                        result = self.query_with_config(query, doc_id, ret_config)
                        
                        if "error" in result:
                            print(f"   ❌ Error: {result['error']}")
                            continue
                        
                        citations = result.get('citations', [])
                        similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                        avg_sim = sum(similarities) / len(similarities) if similarities else 0
                        max_sim = max(similarities) if similarities else 0
                        
                        answer = result.get('answer', '')
                        quality, has_relevant = self.evaluate_answer(answer, query, query_set['keywords'])
                        
                        test_result = TestResult(
                            ingestion=ing_config,
                            retrieval=ret_config,
                            query=query,
                            query_language=lang,
                            document_name=doc_name,
                            chunks_created=doc_info['chunks'],
                            ingestion_time=doc_info['ingestion_time'],
                            citations_count=len(citations),
                            avg_similarity=avg_sim,
                            max_similarity=max_sim,
                            response_time=result.get('response_time', 0),
                            answer_quality=quality,
                            answer_length=len(answer),
                            has_relevant_info=has_relevant
                        )
                        
                        self.results.append(test_result)
                        test_count += 1
                        
                        status = "✅" if quality >= 60 else "⚠️" if quality >= 40 else "❌"
                        print(f"   {status} {ret_config.search_mode:8s} sw={ret_config.semantic_weight:.1f} k={ret_config.k:2d} {lang:7s} | "
                              f"C:{len(citations):2d} S:{avg_sim:5.1f}% Q:{quality:5.1f}%")
                        
                        time.sleep(0.5)
        
        print(f"\n✅ Completed {test_count} total tests")
        
        # Analyze results
        return self.analyze_comprehensive_results()
    
    def test_existing_documents(self, retrieval_configs: List[RetrievalConfig], test_queries: List[Dict]) -> Dict:
        """Test retrieval on existing documents"""
        print("\n📚 Testing with existing documents...")
        
        # Get existing documents
        response = requests.get(f"{self.base_url}/documents", timeout=30)
        docs = response.json()
        if isinstance(docs, dict) and "documents" in docs:
            docs = docs["documents"]
        
        spanish_docs = []
        for doc in docs:
            if hasattr(doc, 'dict'):
                doc = doc.dict()
            elif hasattr(doc, '__dict__'):
                doc = doc.__dict__
            
            if isinstance(doc, dict):
                doc_name = doc.get('document_name', '').lower() if doc.get('document_name') else ''
                if 'vuormar' in doc_name or 'em10' in doc_name or 'em11' in doc_name:
                    spanish_docs.append(doc)
        
        if not spanish_docs:
            return {"error": "No test documents available"}
        
        print(f"Found {len(spanish_docs)} Spanish document(s)")
        
        # Test retrieval only
        for doc in spanish_docs[:3]:  # Test first 3
            doc_id = doc.get('document_id')
            doc_name = doc.get('document_name')
            
            print(f"\n📄 {doc_name}")
            
            for ret_config in retrieval_configs[:10]:
                for query_set in test_queries[:2]:
                    for lang, query in [("Spanish", query_set["spanish"]), ("English", query_set["english"])]:
                        result = self.query_with_config(query, doc_id, ret_config)
                        
                        if "error" in result:
                            continue
                        
                        citations = result.get('citations', [])
                        similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                        avg_sim = sum(similarities) / len(similarities) if similarities else 0
                        
                        answer = result.get('answer', '')
                        quality, has_relevant = self.evaluate_answer(answer, query, query_set['keywords'])
                        
                        # Create dummy ingestion config for existing docs
                        ing_config = IngestionConfig("unknown", 512, 128)
                        
                        test_result = TestResult(
                            ingestion=ing_config,
                            retrieval=ret_config,
                            query=query,
                            query_language=lang,
                            document_name=doc_name,
                            chunks_created=doc.get('chunks_created', 0),
                            ingestion_time=0,
                            citations_count=len(citations),
                            avg_similarity=avg_sim,
                            max_similarity=max(similarities) if similarities else 0,
                            response_time=result.get('response_time', 0),
                            answer_quality=quality,
                            answer_length=len(answer),
                            has_relevant_info=has_relevant
                        )
                        
                        self.results.append(test_result)
                        
                        time.sleep(0.5)
        
        return self.analyze_comprehensive_results()
    
    def analyze_comprehensive_results(self) -> Dict:
        """Analyze all test results"""
        if not self.results:
            return {"error": "No results to analyze"}
        
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE ANALYSIS")
        print("=" * 80)
        
        # Group by ingestion parameters
        by_chunk_size = {}
        by_chunk_overlap = {}
        by_parser = {}
        
        # Group by retrieval parameters
        by_search_mode = {}
        by_semantic_weight = {}
        by_k = {}
        by_mmr = {}
        by_temperature = {}
        by_agentic = {}
        
        for r in self.results:
            quality = r.answer_quality
            
            # Ingestion grouping
            cs = r.ingestion.chunk_size
            if cs not in by_chunk_size:
                by_chunk_size[cs] = []
            by_chunk_size[cs].append(quality)
            
            co = r.ingestion.chunk_overlap
            if co not in by_chunk_overlap:
                by_chunk_overlap[co] = []
            by_chunk_overlap[co].append(quality)
            
            parser = r.ingestion.parser
            if parser not in by_parser:
                by_parser[parser] = []
            by_parser[parser].append(quality)
            
            # Retrieval grouping
            mode = r.retrieval.search_mode
            if mode not in by_search_mode:
                by_search_mode[mode] = []
            by_search_mode[mode].append(quality)
            
            sw = r.retrieval.semantic_weight
            if sw not in by_semantic_weight:
                by_semantic_weight[sw] = []
            by_semantic_weight[sw].append(quality)
            
            k = r.retrieval.k
            if k not in by_k:
                by_k[k] = []
            by_k[k].append(quality)
            
            mmr = r.retrieval.use_mmr
            if mmr not in by_mmr:
                by_mmr[mmr] = []
            by_mmr[mmr].append(quality)
            
            temp = r.retrieval.temperature
            if temp not in by_temperature:
                by_temperature[temp] = []
            by_temperature[temp].append(quality)
            
            agentic = r.retrieval.use_agentic_rag
            if agentic not in by_agentic:
                by_agentic[agentic] = []
            by_agentic[agentic].append(quality)
        
        # Calculate averages and display
        print("\n📦 INGESTION PARAMETERS:")
        print("\n  Chunk Size:")
        chunk_size_avgs = []
        for cs in sorted(by_chunk_size.keys()):
            qualities = by_chunk_size[cs]
            avg = statistics.mean(qualities)
            chunk_size_avgs.append((cs, avg))
            print(f"    {cs:4d}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n  Chunk Overlap:")
        chunk_overlap_avgs = []
        for co in sorted(by_chunk_overlap.keys()):
            qualities = by_chunk_overlap[co]
            avg = statistics.mean(qualities)
            chunk_overlap_avgs.append((co, avg))
            print(f"    {co:3d}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n  Parser:")
        parser_avgs = []
        for parser in sorted(by_parser.keys()):
            qualities = by_parser[parser]
            avg = statistics.mean(qualities)
            parser_avgs.append((parser, avg))
            print(f"    {parser:12s}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n🔍 RETRIEVAL PARAMETERS:")
        print("\n  Search Mode:")
        mode_avgs = []
        for mode in sorted(by_search_mode.keys()):
            qualities = by_search_mode[mode]
            avg = statistics.mean(qualities)
            mode_avgs.append((mode, avg))
            print(f"    {mode:10s}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n  Semantic Weight:")
        sw_avgs = []
        for sw in sorted(by_semantic_weight.keys(), reverse=True):
            qualities = by_semantic_weight[sw]
            avg = statistics.mean(qualities)
            sw_avgs.append((sw, avg))
            print(f"    {sw:.1f}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n  K Value:")
        k_avgs = []
        for k in sorted(by_k.keys()):
            qualities = by_k[k]
            avg = statistics.mean(qualities)
            k_avgs.append((k, avg))
            print(f"    {k:2d}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n  MMR:")
        mmr_avgs = []
        for mmr in [False, True]:
            if mmr in by_mmr:
                qualities = by_mmr[mmr]
                avg = statistics.mean(qualities)
                mmr_avgs.append((mmr, avg))
                status = "Enabled" if mmr else "Disabled"
                print(f"    {status:10s}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n  Temperature:")
        temp_avgs = []
        for temp in sorted(by_temperature.keys()):
            qualities = by_temperature[temp]
            avg = statistics.mean(qualities)
            temp_avgs.append((temp, avg))
            print(f"    {temp:.1f}: {avg:5.1f}% ({len(qualities)} tests)")
        
        print("\n  Agentic RAG:")
        agentic_avgs = []
        for agentic in [False, True]:
            if agentic in by_agentic:
                qualities = by_agentic[agentic]
                avg = statistics.mean(qualities)
                agentic_avgs.append((agentic, avg))
                status = "Enabled" if agentic else "Disabled"
                print(f"    {status:10s}: {avg:5.1f}% ({len(qualities)} tests)")
        
        # Find best configuration
        best_chunk_size = max(chunk_size_avgs, key=lambda x: x[1])[0] if chunk_size_avgs else 512
        best_chunk_overlap = max(chunk_overlap_avgs, key=lambda x: x[1])[0] if chunk_overlap_avgs else 128
        best_parser = max(parser_avgs, key=lambda x: x[1])[0] if parser_avgs else "pymupdf"
        best_mode = max(mode_avgs, key=lambda x: x[1])[0] if mode_avgs else "hybrid"
        best_sw = max(sw_avgs, key=lambda x: x[1])[0] if sw_avgs else 0.4
        best_k = max(k_avgs, key=lambda x: x[1])[0] if k_avgs else 20
        best_mmr = max(mmr_avgs, key=lambda x: x[1])[0] if mmr_avgs else False
        best_temp = max(temp_avgs, key=lambda x: x[1])[0] if temp_avgs else 0.2
        best_agentic = max(agentic_avgs, key=lambda x: x[1])[0] if agentic_avgs else False
        
        print("\n" + "=" * 80)
        print("🏆 OPTIMAL CONFIGURATION")
        print("=" * 80)
        
        print("\n📦 INGESTION:")
        print(f"  ✅ Chunk Size: {best_chunk_size} ({dict(chunk_size_avgs).get(best_chunk_size, 0):.1f}%)")
        print(f"  ✅ Chunk Overlap: {best_chunk_overlap} ({dict(chunk_overlap_avgs).get(best_chunk_overlap, 0):.1f}%)")
        print(f"  ✅ Parser: {best_parser} ({dict(parser_avgs).get(best_parser, 0):.1f}%)")
        
        print("\n🔍 RETRIEVAL:")
        print(f"  ✅ Search Mode: {best_mode} ({dict(mode_avgs).get(best_mode, 0):.1f}%)")
        print(f"  ✅ Semantic Weight: {best_sw} ({dict(sw_avgs).get(best_sw, 0):.1f}%)")
        print(f"  ✅ K Value: {best_k} ({dict(k_avgs).get(best_k, 0):.1f}%)")
        print(f"  ✅ MMR: {'Enabled' if best_mmr else 'Disabled'} ({dict(mmr_avgs).get(best_mmr, 0):.1f}%)")
        print(f"  ✅ Temperature: {best_temp} ({dict(temp_avgs).get(best_temp, 0):.1f}%)")
        print(f"  ✅ Agentic RAG: {'Enabled' if best_agentic else 'Disabled'} ({dict(agentic_avgs).get(best_agentic, 0):.1f}%)")
        
        # Generate configuration code
        print("\n" + "=" * 80)
        print("📝 CONFIGURATION CODE")
        print("=" * 80)
        
        print("\n# shared/config/settings.py:")
        print("-" * 80)
        print(f"""
# Ingestion Configuration (Optimized)
DEFAULT_CHUNK_SIZE: int = {best_chunk_size}
DEFAULT_CHUNK_OVERLAP: int = {best_chunk_overlap}
DEFAULT_PARSER: str = '{best_parser}'

# Retrieval Configuration (Optimized)
DEFAULT_SEARCH_MODE: str = '{best_mode}'
DEFAULT_SEMANTIC_WEIGHT: float = {best_sw}
DEFAULT_KEYWORD_WEIGHT: float = {1.0 - best_sw}
DEFAULT_RETRIEVAL_K: int = {best_k}
DEFAULT_USE_MMR: bool = {str(best_mmr)}
DEFAULT_TEMPERATURE: float = {best_temp}
DEFAULT_USE_AGENTIC_RAG: bool = {str(best_agentic)}
        """)
        
        # Return recommendations
        return {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "ingestion": {
                "best_chunk_size": best_chunk_size,
                "best_chunk_overlap": best_chunk_overlap,
                "best_parser": best_parser,
                "chunk_size_performance": {str(k): v for k, v in chunk_size_avgs},
                "chunk_overlap_performance": {str(k): v for k, v in chunk_overlap_avgs},
                "parser_performance": {k: v for k, v in parser_avgs}
            },
            "retrieval": {
                "best_search_mode": best_mode,
                "best_semantic_weight": best_sw,
                "best_k": best_k,
                "best_mmr": best_mmr,
                "best_temperature": best_temp,
                "best_agentic_rag": best_agentic,
                "search_mode_performance": {k: v for k, v in mode_avgs},
                "semantic_weight_performance": {str(k): v for k, v in sw_avgs},
                "k_performance": {str(k): v for k, v in k_avgs},
                "mmr_performance": {str(k): v for k, v in mmr_avgs},
                "temperature_performance": {str(k): v for k, v in temp_avgs},
                "agentic_performance": {str(k): v for k, v in agentic_avgs}
            }
        }
    
    def save_results(self, filename: str = None):
        """Save results to JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_optimization_results_{timestamp}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results],
            "analysis": self.analyze_comprehensive_results()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {filename}")
        return filename

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive system optimization")
    parser.add_argument("--docs-dir", default="docs/testing/clientSpanishDocs", help="Directory with test PDFs")
    parser.add_argument("--url", default=BASE_URL, help="Base URL of the API")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    optimizer = SystemOptimizer(base_url=args.url)
    
    try:
        print("\n⏱️  This will take 30-60 minutes for comprehensive testing...")
        print("Testing both ingestion AND retrieval parameters\n")
        
        recommendations = optimizer.run_comprehensive_test(args.docs_dir)
        
        if args.save:
            optimizer.save_results()
        
        print("\n" + "=" * 80)
        print("✅ OPTIMIZATION COMPLETE")
        print("=" * 80)
        print("\nApply the recommended configuration to shared/config/settings.py")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user.")
        if optimizer.results:
            print(f"Partial results: {len(optimizer.results)} tests completed")
            if args.save:
                optimizer.save_results()
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

