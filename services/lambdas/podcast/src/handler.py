import json
from typing import Any, Dict


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    # Placeholder Lambda handler
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "podcast lambda ok"}),
    }


