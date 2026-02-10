"""
Unit tests for chunking strategies
"""
import pytest
from shared.utils.chunking_strategies import (
    get_strategy,
    get_chunking_params,
    get_all_strategies,
    validate_custom_params,
    CHUNKING_STRATEGIES
)


@pytest.mark.unit
class TestChunkingStrategies:
    """Test chunking strategy functions"""
    
    def test_get_strategy_precise(self):
        """Test getting precise strategy"""
        strategy = get_strategy("precise")
        assert strategy is not None
        assert strategy["name"] == "Precise"
        assert strategy["chunk_size"] == 256
        assert strategy["chunk_overlap"] == 50
    
    def test_get_strategy_balanced(self):
        """Test getting balanced strategy"""
        strategy = get_strategy("balanced")
        assert strategy is not None
        assert strategy["name"] == "Balanced"
        assert strategy["chunk_size"] == 384
        assert strategy["chunk_overlap"] == 75
    
    def test_get_strategy_comprehensive(self):
        """Test getting comprehensive strategy"""
        strategy = get_strategy("comprehensive")
        assert strategy is not None
        assert strategy["name"] == "Comprehensive"
        assert strategy["chunk_size"] == 512
        assert strategy["chunk_overlap"] == 100
    
    def test_get_strategy_case_insensitive(self):
        """Test strategy lookup is case insensitive"""
        assert get_strategy("PRECISE") is not None
        assert get_strategy("Balanced") is not None
        assert get_strategy("COMPREHENSIVE") is not None
    
    def test_get_strategy_invalid(self):
        """Test getting invalid strategy"""
        strategy = get_strategy("invalid")
        assert strategy is None
    
    def test_get_chunking_params_precise(self):
        """Test getting chunking parameters for precise"""
        chunk_size, chunk_overlap = get_chunking_params("precise")
        assert chunk_size == 256
        assert chunk_overlap == 50
    
    def test_get_chunking_params_balanced(self):
        """Test getting chunking parameters for balanced"""
        chunk_size, chunk_overlap = get_chunking_params("balanced")
        assert chunk_size == 384
        assert chunk_overlap == 75
    
    def test_get_chunking_params_comprehensive(self):
        """Test getting chunking parameters for comprehensive"""
        chunk_size, chunk_overlap = get_chunking_params("comprehensive")
        assert chunk_size == 512
        assert chunk_overlap == 100
    
    def test_get_chunking_params_invalid_defaults(self):
        """Test invalid strategy defaults to comprehensive"""
        chunk_size, chunk_overlap = get_chunking_params("invalid")
        # Should default to comprehensive
        assert chunk_size == 512
        assert chunk_overlap == 100
    
    def test_get_all_strategies(self):
        """Test getting all strategies"""
        strategies = get_all_strategies()
        assert isinstance(strategies, dict)
        assert "precise" in strategies
        assert "balanced" in strategies
        assert "comprehensive" in strategies
        assert len(strategies) == 3
    
    def test_validate_custom_params_valid(self):
        """Test validating valid custom parameters"""
        is_valid, warning = validate_custom_params(384, 75)
        assert is_valid is True
        assert warning is None
    
    def test_validate_custom_params_invalid_size(self):
        """Test validating invalid chunk size"""
        is_valid, warning = validate_custom_params(0, 10)
        assert is_valid is False
        assert "must be at least 1" in warning
    
    def test_validate_custom_params_negative_overlap(self):
        """Test validating negative overlap"""
        is_valid, warning = validate_custom_params(100, -1)
        assert is_valid is False
        assert "cannot be negative" in warning
    
    def test_validate_custom_params_small_chunk_warning(self):
        """Test warning for very small chunk size"""
        is_valid, warning = validate_custom_params(30, 5)
        assert is_valid is True
        assert warning is not None
        assert "small chunk size" in warning.lower()
    
    def test_validate_custom_params_large_chunk_warning(self):
        """Test warning for very large chunk size"""
        is_valid, warning = validate_custom_params(6000, 100)
        assert is_valid is True
        assert warning is not None
        assert "large chunk size" in warning.lower()
    
    def test_validate_custom_params_high_overlap_warning(self):
        """Test warning for high overlap"""
        is_valid, warning = validate_custom_params(100, 90)
        assert is_valid is True
        assert warning is not None
        assert "overlap" in warning.lower()
    
    def test_validate_custom_params_overlap_equals_size(self):
        """Test warning when overlap equals chunk size"""
        is_valid, warning = validate_custom_params(100, 100)
        assert is_valid is True
        assert warning is not None
        assert "overlap" in warning.lower() or ">=" in warning
    
    def test_strategy_structure(self):
        """Test that all strategies have required fields"""
        required_fields = ["name", "chunk_size", "chunk_overlap", "description", "use_case"]
        
        for strategy_name, strategy in CHUNKING_STRATEGIES.items():
            for field in required_fields:
                assert field in strategy, f"Strategy {strategy_name} missing field {field}"
                assert strategy[field] is not None, f"Strategy {strategy_name} field {field} is None"
    
    def test_strategy_chunk_size_positive(self):
        """Test that all strategies have positive chunk sizes"""
        for strategy_name, strategy in CHUNKING_STRATEGIES.items():
            assert strategy["chunk_size"] > 0, f"Strategy {strategy_name} has non-positive chunk_size"
            assert strategy["chunk_overlap"] >= 0, f"Strategy {strategy_name} has negative overlap"
            assert strategy["chunk_overlap"] < strategy["chunk_size"], \
                f"Strategy {strategy_name} has overlap >= chunk_size"
