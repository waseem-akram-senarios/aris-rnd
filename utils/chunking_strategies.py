"""
Chunking Strategy Presets
Predefined chunking strategies for document processing.
"""
from typing import Dict, Tuple, Optional

# Chunking strategy presets
CHUNKING_STRATEGIES: Dict[str, Dict[str, any]] = {
    "precise": {
        "name": "Precise",
        "chunk_size": 256,
        "chunk_overlap": 50,
        "description": "Small chunks for exact matches. Best for precise retrieval and specific fact extraction.",
        "use_case": "Use when you need very specific, targeted information. Creates more chunks but with higher precision."
    },
    "balanced": {
        "name": "Balanced",
        "chunk_size": 384,
        "chunk_overlap": 75,
        "description": "Medium chunks with good balance. Recommended default for most use cases.",
        "use_case": "Best general-purpose option. Good balance between precision and context."
    },
    "comprehensive": {
        "name": "Comprehensive",
        "chunk_size": 512,
        "chunk_overlap": 100,
        "description": "Larger chunks with more context. Better for complex queries requiring broader understanding.",
        "use_case": "Use for complex questions that need more context. Fewer chunks but richer information per chunk."
    }
}


def get_strategy(strategy_name: str) -> Optional[Dict[str, any]]:
    """
    Get chunking strategy by name.
    
    Args:
        strategy_name: Name of the strategy ("precise", "balanced", "comprehensive")
    
    Returns:
        Strategy dictionary or None if not found
    """
    return CHUNKING_STRATEGIES.get(strategy_name.lower())


def get_chunking_params(strategy_name: str) -> Tuple[int, int]:
    """
    Get chunk_size and chunk_overlap for a strategy.
    
    Args:
        strategy_name: Name of the strategy
    
    Returns:
        Tuple of (chunk_size, chunk_overlap)
    """
    strategy = get_strategy(strategy_name)
    if strategy:
        return (strategy["chunk_size"], strategy["chunk_overlap"])
    # Default to comprehensive (optimized for large documents) if not found
    return (CHUNKING_STRATEGIES["comprehensive"]["chunk_size"], 
            CHUNKING_STRATEGIES["comprehensive"]["chunk_overlap"])


def get_all_strategies() -> Dict[str, Dict[str, any]]:
    """
    Get all available chunking strategies.
    
    Returns:
        Dictionary of all strategies
    """
    return CHUNKING_STRATEGIES.copy()


def validate_custom_params(chunk_size: int, chunk_overlap: int) -> Tuple[bool, Optional[str]]:
    """
    Validate custom chunking parameters (warnings only, no hard limits).
    
    Args:
        chunk_size: Size of chunks in tokens
        chunk_overlap: Overlap between chunks in tokens
    
    Returns:
        Tuple of (is_valid, warning_message)
        Always returns True (allows any values), but may return warnings
    """
    warnings = []
    
    if chunk_size < 1:
        return (False, "Chunk size must be at least 1 token")
    if chunk_overlap < 0:
        return (False, "Chunk overlap cannot be negative")
    
    # Warnings (not errors) for unusual configurations
    if chunk_size < 50:
        warnings.append(f"Very small chunk size ({chunk_size} tokens) may lose context")
    if chunk_size > 5000:
        warnings.append(f"Very large chunk size ({chunk_size} tokens) may impact precision")
    if chunk_overlap >= chunk_size:
        warnings.append(f"Overlap ({chunk_overlap}) >= chunk size ({chunk_size}) may cause excessive overlap")
    elif chunk_overlap > chunk_size * 0.8:
        warnings.append(f"High overlap ({chunk_overlap}/{chunk_size} = {chunk_overlap/chunk_size*100:.1f}%) may reduce chunk diversity")
    
    if warnings:
        return (True, "; ".join(warnings))
    return (True, None)

