"""
Comprehensive metrics collector for R&D analytics.
Tracks document processing, queries, costs, and system performance.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict


@dataclass
class QueryMetrics:
    """Metrics for a single query."""
    question: str
    answer_length: int
    response_time: float
    chunks_used: int
    sources_count: int
    timestamp: datetime = field(default_factory=datetime.now)
    api_used: str = "openai"  # 'openai' or 'cerebras'
    success: bool = True
    error: Optional[str] = None
    context_tokens: int = 0  # Tokens in retrieved context
    response_tokens: int = 0  # Tokens in LLM response
    total_tokens: int = 0  # Total tokens (context + response)


@dataclass
class ProcessingMetrics:
    """Metrics for document processing."""
    document_name: str
    file_size: int  # bytes
    file_type: str
    parser_used: str
    pages: int
    chunks_created: int
    tokens_extracted: int
    extraction_percentage: float
    confidence: float
    processing_time: float
    parsing_time: float = 0.0
    chunking_time: float = 0.0
    embedding_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None
    images_detected: bool = False


class MetricsCollector:
    """Collects and aggregates metrics for R&D analysis."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.processing_metrics: List[ProcessingMetrics] = []
        self.query_metrics: List[QueryMetrics] = []
        self.errors: List[Dict] = []
        
        # Aggregated statistics
        self._parser_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'total_tokens': 0,
            'total_chunks': 0,
            'success_count': 0,
            'avg_confidence': 0.0,
            'avg_extraction': 0.0
        })
        
        self._file_type_stats: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'total_size': 0,
            'total_time': 0.0,
            'total_tokens': 0
        })
    
    def record_processing(
        self,
        document_name: str,
        file_size: int,
        file_type: str,
        parser_used: str,
        pages: int,
        chunks_created: int,
        tokens_extracted: int,
        extraction_percentage: float,
        confidence: float,
        processing_time: float,
        parsing_time: float = 0.0,
        chunking_time: float = 0.0,
        embedding_time: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
        images_detected: bool = False
    ):
        """Record document processing metrics."""
        metric = ProcessingMetrics(
            document_name=document_name,
            file_size=file_size,
            file_type=file_type,
            parser_used=parser_used,
            pages=pages,
            chunks_created=chunks_created,
            tokens_extracted=tokens_extracted,
            extraction_percentage=extraction_percentage,
            confidence=confidence,
            processing_time=processing_time,
            parsing_time=parsing_time,
            chunking_time=chunking_time,
            embedding_time=embedding_time,
            success=success,
            error=error,
            images_detected=images_detected
        )
        
        self.processing_metrics.append(metric)
        
        # Update parser statistics
        parser_stat = self._parser_stats[parser_used]
        parser_stat['count'] += 1
        parser_stat['total_time'] += processing_time
        parser_stat['total_tokens'] += tokens_extracted
        parser_stat['total_chunks'] += chunks_created
        if success:
            parser_stat['success_count'] += 1
        parser_stat['avg_confidence'] = (
            (parser_stat['avg_confidence'] * (parser_stat['count'] - 1) + confidence) 
            / parser_stat['count']
        )
        parser_stat['avg_extraction'] = (
            (parser_stat['avg_extraction'] * (parser_stat['count'] - 1) + extraction_percentage) 
            / parser_stat['count']
        )
        
        # Update file type statistics
        file_stat = self._file_type_stats[file_type]
        file_stat['count'] += 1
        file_stat['total_size'] += file_size
        file_stat['total_time'] += processing_time
        file_stat['total_tokens'] += tokens_extracted
        
        if error:
            self.errors.append({
                'type': 'processing',
                'document': document_name,
                'parser': parser_used,
                'error': error,
                'timestamp': datetime.now()
            })
    
    def record_query(
        self,
        question: str,
        answer_length: int,
        response_time: float,
        chunks_used: int,
        sources_count: int,
        api_used: str = "openai",
        success: bool = True,
        error: Optional[str] = None,
        context_tokens: int = 0,
        response_tokens: int = 0,
        total_tokens: int = 0
    ):
        """Record query metrics."""
        metric = QueryMetrics(
            question=question,
            answer_length=answer_length,
            response_time=response_time,
            chunks_used=chunks_used,
            sources_count=sources_count,
            api_used=api_used,
            success=success,
            error=error,
            context_tokens=context_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens
        )
        
        self.query_metrics.append(metric)
        
        if error:
            self.errors.append({
                'type': 'query',
                'question': question[:50],
                'api': api_used,
                'error': error,
                'timestamp': datetime.now()
            })
    
    def get_processing_stats(self) -> Dict:
        """Get aggregated processing statistics."""
        if not self.processing_metrics:
            return {}
        
        total_docs = len(self.processing_metrics)
        successful = sum(1 for m in self.processing_metrics if m.success)
        
        total_tokens = sum(m.tokens_extracted for m in self.processing_metrics)
        total_chunks = sum(m.chunks_created for m in self.processing_metrics)
        total_time = sum(m.processing_time for m in self.processing_metrics)
        total_size = sum(m.file_size for m in self.processing_metrics)
        
        avg_processing_time = total_time / total_docs if total_docs > 0 else 0
        avg_tokens_per_doc = total_tokens / total_docs if total_docs > 0 else 0
        avg_chunks_per_doc = total_chunks / total_docs if total_docs > 0 else 0
        avg_extraction = sum(m.extraction_percentage for m in self.processing_metrics) / total_docs if total_docs > 0 else 0
        avg_confidence = sum(m.confidence for m in self.processing_metrics) / total_docs if total_docs > 0 else 0
        
        return {
            'total_documents': total_docs,
            'successful_documents': successful,
            'failed_documents': total_docs - successful,
            'success_rate': successful / total_docs if total_docs > 0 else 0,
            'total_tokens': total_tokens,
            'total_chunks': total_chunks,
            'total_processing_time': total_time,
            'total_file_size': total_size,
            'avg_processing_time': avg_processing_time,
            'avg_tokens_per_document': avg_tokens_per_doc,
            'avg_chunks_per_document': avg_chunks_per_doc,
            'avg_extraction_percentage': avg_extraction,
            'avg_confidence': avg_confidence,
            'parser_statistics': dict(self._parser_stats),
            'file_type_statistics': dict(self._file_type_stats)
        }
    
    def get_query_stats(self) -> Dict:
        """Get aggregated query statistics."""
        if not self.query_metrics:
            return {}
        
        total_queries = len(self.query_metrics)
        successful = sum(1 for m in self.query_metrics if m.success)
        
        total_response_time = sum(m.response_time for m in self.query_metrics)
        total_answer_length = sum(m.answer_length for m in self.query_metrics)
        total_chunks_used = sum(m.chunks_used for m in self.query_metrics)
        
        avg_response_time = total_response_time / total_queries if total_queries > 0 else 0
        avg_answer_length = total_answer_length / total_queries if total_queries > 0 else 0
        avg_chunks_per_query = total_chunks_used / total_queries if total_queries > 0 else 0
        
        # API usage statistics
        api_usage = defaultdict(int)
        for m in self.query_metrics:
            api_usage[m.api_used] += 1
        
        # Token statistics
        total_context_tokens = sum(m.context_tokens for m in self.query_metrics)
        total_response_tokens = sum(m.response_tokens for m in self.query_metrics)
        total_query_tokens = sum(m.total_tokens for m in self.query_metrics)
        avg_context_tokens = total_context_tokens / total_queries if total_queries > 0 else 0
        avg_response_tokens = total_response_tokens / total_queries if total_queries > 0 else 0
        avg_total_tokens = total_query_tokens / total_queries if total_queries > 0 else 0
        
        return {
            'total_queries': total_queries,
            'successful_queries': successful,
            'failed_queries': total_queries - successful,
            'success_rate': successful / total_queries if total_queries > 0 else 0,
            'total_response_time': total_response_time,
            'avg_response_time': avg_response_time,
            'avg_answer_length': avg_answer_length,
            'avg_chunks_per_query': avg_chunks_per_query,
            'api_usage': dict(api_usage),
            'total_context_tokens': total_context_tokens,
            'total_response_tokens': total_response_tokens,
            'total_query_tokens': total_query_tokens,
            'avg_context_tokens': avg_context_tokens,
            'avg_response_tokens': avg_response_tokens,
            'avg_total_tokens': avg_total_tokens
        }
    
    def get_cost_analysis(self) -> Dict:
        """Calculate cost breakdown."""
        # Embedding costs (text-embedding-3-small: $0.02 per 1M tokens)
        total_tokens = sum(m.tokens_extracted for m in self.processing_metrics)
        embedding_cost = (total_tokens / 1_000_000) * 0.02
        
        # Query costs (approximate)
        # GPT-3.5-turbo: ~$0.0015 per 1K tokens (input + output)
        query_cost = 0.0
        for q in self.query_metrics:
            if q.api_used == 'openai':
                # Rough estimate: ~500 tokens per query average
                estimated_tokens = 500
                query_cost += (estimated_tokens / 1000) * 0.0015
        
        total_cost = embedding_cost + query_cost
        
        return {
            'embedding_cost_usd': embedding_cost,
            'query_cost_usd': query_cost,
            'total_cost_usd': total_cost,
            'total_tokens_embedded': total_tokens,
            'total_queries': len(self.query_metrics),
            'cost_per_document': embedding_cost / len(self.processing_metrics) if self.processing_metrics else 0,
            'cost_per_query': query_cost / len(self.query_metrics) if self.query_metrics else 0
        }
    
    def get_parser_comparison(self) -> Dict:
        """Compare parser performance."""
        comparison = {}
        
        for parser, stats in self._parser_stats.items():
            comparison[parser] = {
                'usage_count': stats['count'],
                'success_rate': stats['success_count'] / stats['count'] if stats['count'] > 0 else 0,
                'avg_processing_time': stats['total_time'] / stats['count'] if stats['count'] > 0 else 0,
                'avg_tokens_per_doc': stats['total_tokens'] / stats['count'] if stats['count'] > 0 else 0,
                'avg_chunks_per_doc': stats['total_chunks'] / stats['count'] if stats['count'] > 0 else 0,
                'avg_confidence': stats['avg_confidence'],
                'avg_extraction_percentage': stats['avg_extraction']
            }
        
        return comparison
    
    def get_performance_trends(self) -> Dict:
        """Get performance trends over time."""
        if not self.processing_metrics:
            return {}
        
        # Sort by timestamp
        sorted_metrics = sorted(self.processing_metrics, key=lambda x: x.timestamp)
        
        # Calculate trends (first half vs second half)
        mid_point = len(sorted_metrics) // 2
        first_half = sorted_metrics[:mid_point] if mid_point > 0 else []
        second_half = sorted_metrics[mid_point:] if mid_point > 0 else []
        
        def avg_time(metrics):
            return sum(m.processing_time for m in metrics) / len(metrics) if metrics else 0
        
        return {
            'first_half_avg_time': avg_time(first_half),
            'second_half_avg_time': avg_time(second_half),
            'trend': 'improving' if avg_time(second_half) < avg_time(first_half) else 'stable' if avg_time(second_half) == avg_time(first_half) else 'degrading'
        }
    
    def get_all_metrics(self) -> Dict:
        """Get comprehensive metrics summary."""
        return {
            'processing': self.get_processing_stats(),
            'queries': self.get_query_stats(),
            'costs': self.get_cost_analysis(),
            'parser_comparison': self.get_parser_comparison(),
            'performance_trends': self.get_performance_trends(),
            'error_summary': {
                'total_errors': len(self.errors),
                'processing_errors': sum(1 for e in self.errors if e['type'] == 'processing'),
                'query_errors': sum(1 for e in self.errors if e['type'] == 'query')
            }
        }
    
    def clear(self):
        """Clear all metrics."""
        self.processing_metrics.clear()
        self.query_metrics.clear()
        self.errors.clear()
        self._parser_stats.clear()
        self._file_type_stats.clear()
    
    def export_to_dict(self) -> Dict:
        """Export metrics to dictionary for JSON serialization."""
        return {
            'processing_metrics': [
                {
                    'document_name': m.document_name,
                    'file_size': m.file_size,
                    'file_type': m.file_type,
                    'parser_used': m.parser_used,
                    'pages': m.pages,
                    'chunks_created': m.chunks_created,
                    'tokens_extracted': m.tokens_extracted,
                    'extraction_percentage': m.extraction_percentage,
                    'confidence': m.confidence,
                    'processing_time': m.processing_time,
                    'timestamp': m.timestamp.isoformat(),
                    'success': m.success,
                    'images_detected': m.images_detected
                }
                for m in self.processing_metrics
            ],
            'query_metrics': [
                {
                    'question': q.question,
                    'answer_length': q.answer_length,
                    'response_time': q.response_time,
                    'chunks_used': q.chunks_used,
                    'sources_count': q.sources_count,
                    'api_used': q.api_used,
                    'timestamp': q.timestamp.isoformat(),
                    'success': q.success,
                    'context_tokens': q.context_tokens,
                    'response_tokens': q.response_tokens,
                    'total_tokens': q.total_tokens
                }
                for q in self.query_metrics
            ],
            'summary': self.get_all_metrics()
        }


