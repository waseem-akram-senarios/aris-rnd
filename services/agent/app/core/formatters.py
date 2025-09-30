"""
Smart, metadata-driven result formatters for tool outputs.

This module provides a flexible, extensible system for formatting tool results
based on their structure and metadata, eliminating hardcoded tool-specific logic.
"""
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import logging


@dataclass
class FormatterResult:
    """Result from a formatter."""
    formatted_text: str
    extracted_files: Optional[List[Dict[str, str]]] = None
    success: bool = True


class ResultFormatter:
    """Smart formatter that uses patterns and metadata to format tool results."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._pattern_formatters = self._register_pattern_formatters()
    
    def _register_pattern_formatters(self) -> List[Callable]:
        """Register pattern-based formatters in priority order."""
        return [
            self._format_file_result,
            self._format_data_collection,
            self._format_structured_data,
            self._format_success_error,
        ]
    
    def format_tool_result(
        self, 
        tool_name: str, 
        result_data: Any,
        tool_metadata: Optional[Dict[str, Any]] = None
    ) -> FormatterResult:
        """
        Format a tool result using pattern matching and metadata.
        
        Args:
            tool_name: Name of the tool
            result_data: The tool's result data
            tool_metadata: Optional metadata from tool definition (tags, meta, etc.)
            
        Returns:
            FormatterResult with formatted text and extracted files
        """
        if not isinstance(result_data, dict):
            return FormatterResult(
                formatted_text=f"Result: {str(result_data)[:200]}",
                success=True
            )
        
        # Try each pattern formatter in order
        for formatter in self._pattern_formatters:
            try:
                result = formatter(tool_name, result_data, tool_metadata)
                if result:
                    return result
            except Exception as e:
                self.logger.debug(f"Formatter {formatter.__name__} skipped: {e}")
                continue
        
        # Fallback: generic formatting
        return self._format_generic(tool_name, result_data)
    
    def _format_file_result(
        self, 
        tool_name: str, 
        result_data: Dict[str, Any],
        tool_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[FormatterResult]:
        """Format results that contain file information (PDFs, Excel, etc.)."""
        # Check for file-related fields
        file_url = result_data.get("file_url") or result_data.get("download_url")
        if not file_url:
            return None
        
        file_name = (
            result_data.get("file_name") or 
            result_data.get("filename") or 
            result_data.get("name") or 
            "document"
        )
        
        file_type = result_data.get("file_type", "file")
        
        return FormatterResult(
            formatted_text=f"Created {file_type}: {file_name} (Download: {file_url})",
            extracted_files=[{"name": file_name, "url": file_url}],
            success=True
        )
    
    def _format_data_collection(
        self, 
        tool_name: str, 
        result_data: Dict[str, Any],
        tool_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[FormatterResult]:
        """Format results that contain collections of structured data."""
        # Detect if this is a data collection result
        # Common patterns: has top-level collections like facility, production_lines, etc.
        
        data_indicators = [
            "facility", "production_lines", "daily_metrics", 
            "inventory", "alerts", "energy_consumption",
            "data", "items", "records"
        ]
        
        # Check if result has multiple data sections
        matching_fields = [field for field in data_indicators if field in result_data]
        if len(matching_fields) < 2:  # Need at least 2 data sections
            return None
        
        # This is a complex data structure - format it nicely
        formatted_parts = []
        formatted_parts.append(f"Retrieved comprehensive data successfully:\n")
        
        # Format each section
        for field in matching_fields:
            value = result_data[field]
            if value is None:
                continue
                
            # Format field name nicely
            field_display = field.replace('_', ' ').title()
            
            if isinstance(value, dict):
                # Format dict data
                formatted_parts.append(f"\n**{field_display}:**")
                formatted_parts.append(self._format_dict_content(value, indent="  "))
            elif isinstance(value, list):
                # Format list data
                formatted_parts.append(f"\n**{field_display}:** ({len(value)} items)")
                if value:
                    # Show first few items
                    for item in value[:3]:
                        if isinstance(item, dict):
                            item_summary = self._get_dict_summary(item)
                            formatted_parts.append(f"  • {item_summary}")
                        else:
                            formatted_parts.append(f"  • {str(item)[:100]}")
                    if len(value) > 3:
                        formatted_parts.append(f"  ... and {len(value) - 3} more")
            else:
                formatted_parts.append(f"**{field_display}:** {value}")
        
        return FormatterResult(
            formatted_text="\n".join(formatted_parts),
            success=True
        )
    
    def _format_structured_data(
        self, 
        tool_name: str, 
        result_data: Dict[str, Any],
        tool_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[FormatterResult]:
        """Format single structured data objects."""
        # Skip if this looks like a simple success/error response
        if set(result_data.keys()).issubset({"success", "error", "message", "status"}):
            return None
        
        # Skip if we already handled this in data_collection
        data_indicators = ["facility", "production_lines", "daily_metrics"]
        if sum(1 for field in data_indicators if field in result_data) >= 2:
            return None
        
        # Format as a simple structured object
        formatted_parts = []
        
        for key, value in result_data.items():
            # Skip internal/metadata fields
            if key in ["success", "error", "status_code", "data_size_kb"]:
                continue
            
            key_display = key.replace('_', ' ').title()
            
            if isinstance(value, (dict, list)):
                if isinstance(value, list):
                    formatted_parts.append(f"• {key_display}: {len(value)} items")
                else:
                    formatted_parts.append(f"• {key_display}: {self._get_dict_summary(value)}")
            else:
                formatted_parts.append(f"• {key_display}: {value}")
        
        if formatted_parts:
            return FormatterResult(
                formatted_text="Retrieved data:\n" + "\n".join(formatted_parts),
                success=True
            )
        
        return None
    
    def _format_success_error(
        self, 
        tool_name: str, 
        result_data: Dict[str, Any],
        tool_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[FormatterResult]:
        """Format simple success/error responses."""
        # Check if this is a success/error result
        has_success = "success" in result_data
        has_error = "error" in result_data
        has_message = "message" in result_data
        
        if not (has_success or has_error or has_message):
            return None
        
        # Format based on success/failure
        if has_error and result_data.get("error"):
            return FormatterResult(
                formatted_text=f"Error: {result_data['error']}",
                success=False
            )
        
        if has_message:
            return FormatterResult(
                formatted_text=result_data["message"],
                success=result_data.get("success", True)
            )
        
        if has_success:
            status = "completed successfully" if result_data["success"] else "failed"
            return FormatterResult(
                formatted_text=f"Operation {status}",
                success=result_data["success"]
            )
        
        return None
    
    def _format_generic(
        self, 
        tool_name: str, 
        result_data: Dict[str, Any]
    ) -> FormatterResult:
        """Generic fallback formatter for any result."""
        # Count meaningful fields
        meaningful_fields = {
            k: v for k, v in result_data.items() 
            if k not in ["success", "error", "status_code"] and v is not None
        }
        
        if len(meaningful_fields) == 0:
            return FormatterResult(
                formatted_text="Operation completed",
                success=result_data.get("success", True)
            )
        
        if len(meaningful_fields) == 1:
            key, value = list(meaningful_fields.items())[0]
            return FormatterResult(
                formatted_text=f"{key.replace('_', ' ').title()}: {value}",
                success=True
            )
        
        # Multiple fields - create summary
        summary_parts = []
        for key, value in list(meaningful_fields.items())[:5]:  # Max 5 fields
            key_display = key.replace('_', ' ').title()
            if isinstance(value, (dict, list)):
                count = len(value)
                summary_parts.append(f"• {key_display}: {count} items")
            else:
                value_str = str(value)[:50]
                summary_parts.append(f"• {key_display}: {value_str}")
        
        return FormatterResult(
            formatted_text="Result:\n" + "\n".join(summary_parts),
            success=True
        )
    
    def _format_dict_content(self, data: Dict[str, Any], indent: str = "") -> str:
        """Format dictionary content with proper indentation."""
        parts = []
        for key, value in list(data.items())[:10]:  # Max 10 fields
            key_display = key.replace('_', ' ').title()
            if isinstance(value, (dict, list)):
                if isinstance(value, list):
                    parts.append(f"{indent}• {key_display}: {len(value)} items")
                else:
                    parts.append(f"{indent}• {key_display}: {len(value)} fields")
            else:
                value_str = str(value)[:100]
                parts.append(f"{indent}• {key_display}: {value_str}")
        return "\n".join(parts)
    
    def _get_dict_summary(self, data: Dict[str, Any]) -> str:
        """Get a one-line summary of a dict."""
        if "name" in data:
            return str(data["name"])
        elif "title" in data:
            return str(data["title"])
        elif "id" in data:
            return f"ID: {data['id']}"
        else:
            # Return first meaningful field
            for key, value in data.items():
                if key not in ["success", "error", "status_code"] and value:
                    return f"{key}: {str(value)[:50]}"
        return f"{len(data)} fields"


# Singleton instance
_formatter_instance = None

def get_formatter() -> ResultFormatter:
    """Get the global formatter instance."""
    global _formatter_instance
    if _formatter_instance is None:
        _formatter_instance = ResultFormatter()
    return _formatter_instance
