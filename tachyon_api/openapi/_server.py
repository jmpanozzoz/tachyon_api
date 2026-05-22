# OpenAPI `servers[]` entry.

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Server:
    url: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"url": self.url}
        if self.description:
            result["description"] = self.description
        return result
