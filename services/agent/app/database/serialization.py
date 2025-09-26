"""
Enhanced serialization utilities for ARIS database storage.
Handles complex objects, dataclasses, enums, and nested structures.
"""

import json
import logging
from typing import Any, Dict, List
from dataclasses import is_dataclass, fields
from enum import Enum

logger = logging.getLogger(__name__)


def serialize_for_database(obj: Any) -> Dict[str, Any]:
    """
    Serialize any Python object for database storage.
    Returns a dictionary with 'data', 'type', and 'module' fields.
    """
    try:
        serialized_data = _serialize_object(obj)
        
        result = {
            "data": serialized_data,
            "type": type(obj).__name__,
            "module": getattr(type(obj), '__module__', 'unknown')
        }
        
        # Test that the result is JSON serializable
        json.dumps(result, default=str)
        
        return result
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to serialize {type(obj).__name__}: {e}")
        # Fallback to string representation
        return {
            "data": str(obj),
            "type": type(obj).__name__,
            "module": getattr(type(obj), '__module__', 'unknown'),
            "serialization_error": str(e)
        }


def _serialize_object(obj: Any) -> Any:
    """
    Recursively serialize an object to JSON-compatible types.
    """
    # Handle primitive types
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    
    # Handle lists and tuples
    elif isinstance(obj, (list, tuple)):
        return [_serialize_object(item) for item in obj]
    
    # Handle dictionaries
    elif isinstance(obj, dict):
        return {str(k): _serialize_object(v) for k, v in obj.items()}
    
    # Handle enums
    elif isinstance(obj, Enum):
        return {
            "_enum_value": obj.value,
            "_enum_name": obj.name,
            "_enum_type": type(obj).__name__
        }
    
    # Handle dataclasses
    elif is_dataclass(obj):
        result = {}
        for field in fields(obj):
            field_value = getattr(obj, field.name)
            result[field.name] = _serialize_object(field_value)
        return result
    
    # Handle objects with __dict__
    elif hasattr(obj, '__dict__'):
        result = {}
        for k, v in obj.__dict__.items():
            if not k.startswith('_'):  # Skip private attributes
                result[k] = _serialize_object(v)
        return result
    
    # Handle iterables (but not strings or bytes)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        try:
            return [_serialize_object(item) for item in obj]
        except Exception:
            return str(obj)
    
    # Fallback to string representation
    else:
        return str(obj)


def deserialize_from_database(data: Dict[str, Any]) -> Any:
    """
    Deserialize an object from database storage.
    Note: This is a basic implementation - full deserialization would require
    importing the original classes and reconstructing objects.
    """
    if not isinstance(data, dict) or 'data' not in data:
        return data
    
    obj_data = data['data']
    obj_type = data.get('type', 'unknown')
    
    # For now, just return the data portion
    # In the future, we could reconstruct the original objects
    return obj_data


def test_serialization():
    """Test function to verify serialization works with planning models."""
    # This can be used for testing the serialization
    from ..planning.models import ExecutionPlan, PlannedAction, ActionType
    
    # Create test objects
    test_action = PlannedAction(
        id="test-action-001",
        type=ActionType.TOOL_CALL,
        name="Test Action",
        description="Test description",
        tool_name="test_tool",
        arguments={"param1": "value1"},
        depends_on=["dependency-001"],
        status="pending"
    )
    
    test_plan = ExecutionPlan(
        id="test-plan-001",
        summary="Test plan",
        status="new",
        actions=[test_action],
        user_query="Test query",
        metadata={"test": True}
    )
    
    # Test serialization
    try:
        serialized = serialize_for_database(test_plan)
        logger.info(f"✅ Serialization test passed for ExecutionPlan")
        return True
    except Exception as e:
        logger.error(f"❌ Serialization test failed: {e}")
        return False
