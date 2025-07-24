"""
Load perpetual contract specs from Mongo *once* at startup.
No external API keys are exposed to end-users.
"""
from dataclasses import dataclass
from typing import Dict, Any

from pymongo import MongoClient

from app.core.pydanticConfig.settings import get_settings

settings = get_settings()

@dataclass(frozen=True)
class PerpSpec:
    symbol: str
    multiplier: float  # contract value in quote currency
    type: str  # "linear" | "inverse"
    max_leverage: float
    mmr: float  # maintenance-margin rate
    funding_intvl: int  # seconds

    @staticmethod
    def from_doc(doc: Dict[str, Any]) -> "PerpSpec":
        return PerpSpec(
            symbol=doc["symbol"],
            multiplier=doc.get("multiplier", 1.0),
            type=doc.get("type", "linear"),
            max_leverage=doc.get("max_leverage", 100),
            mmr=doc.get("mmr", 0.005),
            funding_intvl=doc.get("funding_interval_sec", 28800),
        )


# ---------- singleton loader (read-only) -------------------------------
_client = MongoClient(settings.MONGO_URI)
_specs_c = _client[settings.MONGO_DB]["perp_specs"]

PERP_SPECS: Dict[str, PerpSpec] = {
    d["symbol"]: PerpSpec.from_doc(d) for d in _specs_c.find({})
}
