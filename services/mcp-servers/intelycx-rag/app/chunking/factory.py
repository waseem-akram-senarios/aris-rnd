"""Factory for creating chunking strategy instances."""

import logging
from typing import Dict, Any, Optional

from .base import ChunkingStrategy
from .semantic import SemanticChunker
from .fixed_size import FixedSizeChunker
from .recursive import RecursiveChunker

logger = logging.getLogger(__name__)


class ChunkerFactory:
    """
    Factory for creating chunking strategy instances.
    
    Supported strategies:
    - semantic: Respects sentence and paragraph boundaries (recommended)
    - fixed: Simple fixed-size chunks
    - recursive: Hierarchical splitting with multiple separators
    """
    
    _strategies = {
        "semantic": SemanticChunker,
        "fixed": FixedSizeChunker,
        "fixed_size": FixedSizeChunker,
        "recursive": RecursiveChunker
    }
    
    @classmethod
    def create(
        cls,
        strategy: str,
        config: Optional[Dict[str, Any]] = None
    ) -> ChunkingStrategy:
        """
        Create a chunking strategy instance.
        
        Args:
            strategy: Strategy name (semantic, fixed, recursive)
            config: Configuration dictionary
            
        Returns:
            ChunkingStrategy instance
            
        Raises:
            ValueError: If strategy is not supported
        """
        strategy = strategy.lower()
        
        if strategy not in cls._strategies:
            supported = ", ".join(cls._strategies.keys())
            raise ValueError(
                f"Unsupported chunking strategy: {strategy}. "
                f"Supported strategies: {supported}"
            )
        
        strategy_class = cls._strategies[strategy]
        config = config or {}
        
        logger.info(f"Creating chunking strategy: {strategy}")
        return strategy_class(config)
    
    @classmethod
    def get_supported_strategies(cls) -> list[str]:
        """Get list of supported strategy names."""
        return list(cls._strategies.keys())
    
    @classmethod
    def get_recommended_config(
        cls,
        strategy: str,
        profile: str = "standard"
    ) -> Dict[str, Any]:
        """
        Get recommended configuration for a strategy and profile.
        
        Args:
            strategy: Strategy name
            profile: Configuration profile (economy, standard, premium)
            
        Returns:
            Recommended configuration dictionary
        """
        configs = {
            "semantic": {
                "economy": {
                    "chunk_size": 800,
                    "chunk_overlap": 100,
                    "min_chunk_size": 100,
                    "max_chunk_size": 1500,
                    "respect_paragraphs": True,
                    "respect_headers": False,
                    "preserve_code_blocks": True
                },
                "standard": {
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                    "min_chunk_size": 100,
                    "max_chunk_size": 2000,
                    "respect_paragraphs": True,
                    "respect_headers": True,
                    "preserve_code_blocks": True
                },
                "premium": {
                    "chunk_size": 1200,
                    "chunk_overlap": 300,
                    "min_chunk_size": 150,
                    "max_chunk_size": 2500,
                    "respect_paragraphs": True,
                    "respect_headers": True,
                    "preserve_code_blocks": True
                }
            },
            "fixed": {
                "economy": {
                    "chunk_size": 500,
                    "chunk_overlap": 50,
                    "min_chunk_size": 100,
                    "max_chunk_size": 1000
                },
                "standard": {
                    "chunk_size": 1000,
                    "chunk_overlap": 100,
                    "min_chunk_size": 100,
                    "max_chunk_size": 1500
                },
                "premium": {
                    "chunk_size": 1500,
                    "chunk_overlap": 200,
                    "min_chunk_size": 150,
                    "max_chunk_size": 2000
                }
            },
            "recursive": {
                "economy": {
                    "chunk_size": 800,
                    "chunk_overlap": 100,
                    "min_chunk_size": 100,
                    "max_chunk_size": 1500,
                    "separators": ["\n\n", "\n", " ", ""]
                },
                "standard": {
                    "chunk_size": 1000,
                    "chunk_overlap": 150,
                    "min_chunk_size": 100,
                    "max_chunk_size": 2000,
                    "separators": ["\n\n", "\n", ". ", " ", ""]
                },
                "premium": {
                    "chunk_size": 1200,
                    "chunk_overlap": 250,
                    "min_chunk_size": 150,
                    "max_chunk_size": 2500,
                    "separators": ["\n\n", "\n", ". ", "! ", "? ", " ", ""]
                }
            }
        }
        
        return configs.get(strategy, {}).get(profile, {})

