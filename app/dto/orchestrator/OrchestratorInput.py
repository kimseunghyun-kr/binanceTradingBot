# orchestrator_input.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

# ----------------------------------------------------------------------------
# 1. Generic component spec ---------------------------------------------------
# ----------------------------------------------------------------------------
class ComponentConfig(BaseModel):
    builtin: Optional[str] = None
    module:  Optional[str] = None
    cls:     Optional[str] = Field(None, alias="class")
    params:  Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)  # allow "class" alias

    # ── user must set *either* builtin or module/cls -------------------------
    @field_validator("builtin", mode="after")
    @classmethod
    def _one_of(cls, v, values):
        if not v and not values.get("module"):
            raise ValueError("specify either 'builtin' or 'module'")
        return v

# convenience factories (keep them DRY)
STATIC_FEE     = lambda: ComponentConfig(builtin="static")
ZERO_SLIP      = lambda: ComponentConfig(builtin="zero")
DEFAULT_FILL   = lambda: ComponentConfig(builtin="AggressiveMarketPolicy")
DEFAULT_CAP    = lambda: ComponentConfig(builtin="LegCapacity")
DEFAULT_SIZING = lambda: ComponentConfig(builtin="fixed_fraction")

# ----------------------------------------------------------------------------
# 2. Strategy params ----------------------------------------------------------
# ----------------------------------------------------------------------------
class StrategyParameters(BaseModel):
    name:   str
    params: Dict[str, Any] = Field(default_factory=dict)

# ----------------------------------------------------------------------------
# 3. Orchestrator input  ------------------------------------------------------
# ----------------------------------------------------------------------------
class OrchestratorInput(BaseModel):
    # core
    strategy:        StrategyParameters
    symbols:         List[str]
    interval:        str
    num_iterations:  int = 100

    # timing
    start_date: datetime | None = None
    end_date:   datetime | None = None

    # portfolio
    initial_capital:   float = 10_000.0
    position_size_pct: float = 5.0
    max_positions:     int   = 10

    # risk
    tp_ratio: float = 0.10
    sl_ratio: float = 0.05

    # plug-ins (all zero-arg factories above)
    fee_model:       ComponentConfig = Field(default_factory=STATIC_FEE)
    slippage_model:  ComponentConfig = Field(default_factory=ZERO_SLIP)
    fill_policy:     ComponentConfig = Field(default_factory=DEFAULT_FILL)
    capacity_policy: ComponentConfig = Field(default_factory=DEFAULT_CAP)
    sizing_model:    ComponentConfig = Field(default_factory=DEFAULT_SIZING)

    # execution
    parallel_symbols: int  = 4
    use_perpetuals:   bool = False
    save_charts:      bool = False
    custom_strategy_code: Optional[str] = None

    # --------------------------------------------------------------------- #
    # Validators                                                            #
    # --------------------------------------------------------------------- #
    @field_validator("interval")
    @classmethod
    def _valid_interval(cls, v: str) -> str:
        allowed = {"1m","5m","15m","30m","1h","4h","1d","1w"}
        if v not in allowed:
            raise ValueError(f"interval must be one of {sorted(allowed)}")
        return v

    # accept ISO strings for dates
    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _parse_iso_dt(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    # ------------------------------------------------------------------ #
    # Pydantic config: make .model_dump(mode="json") return JSON-safe    #
    # ------------------------------------------------------------------ #
    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat()}
    )

    def to_container_payload(self) -> Dict[str, Any]:
        """Return a JSON-safe dict the orchestrator script expects."""
        flat = self.model_dump(
            mode="json",  # datetimes → ISO-8601 strings
            exclude={
                "strategy",
                "symbols",
                "interval",
                "num_iterations",
            },
            exclude_none=True,
        )
        return {
            **flat,
            "strategy_config": self.strategy.model_dump(mode="json"),
            "symbols": self.symbols,
            "interval": self.interval,
            "num_iterations": self.num_iterations,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),  # ISO-8601 UTC,
        }

    def signature_json(self) -> str:
        """Deterministic JSON used to derive cache / run-id."""
        import json
        sig = self.model_dump(
            mode="json",
            exclude_none=True,
        )
        return json.dumps(sig, sort_keys=True, separators=(",", ":"))
