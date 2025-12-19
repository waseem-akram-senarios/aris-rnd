"""
ARIS Agent Version Management

Current version: 2.0.0
Version format: MAJOR.MINOR.PATCH (semantic versioning)

Version bumping rules:
- PATCH (2.0.0 -> 2.0.1): Smallest increment for any code change
- MINOR (2.0.0 -> 2.1.0): Medium increment, only upon user request
- MAJOR (2.0.0 -> 3.0.0): Breaking changes, only upon user request
"""

__version__ = "2.0.14"


def get_version() -> str:
    """Get the current ARIS agent version."""
    return __version__


def add_version_to_message(message: dict) -> dict:
    """
    Add version field to a WebSocket message.
    
    Args:
        message: Dictionary representing a WebSocket message
        
    Returns:
        Dictionary with version field added
    """
    if "version" not in message:
        message["version"] = get_version()
    return message

