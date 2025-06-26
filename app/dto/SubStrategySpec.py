from typing import Optional, Dict, Any

from pydantic import BaseModel


class SubStrategySpec(BaseModel):
    name: str
    weight: Optional[float] = 1.0
    params: Optional[Dict[str, Any]] = None
