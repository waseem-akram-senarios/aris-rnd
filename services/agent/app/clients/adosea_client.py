from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ADOSEAClient:
    base_url: str
    api_key: Optional[str] = None

    async def get_production_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Placeholder: implement aiohttp-based call with auth header
        return {"production_data": [], "summary_metrics": {}}


