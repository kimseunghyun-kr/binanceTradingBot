import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.init_services import get_master_db_async
from app.services.StrategyService import StrategyService

router = APIRouter(prefix="/strategies", tags=["Strategies"])


class StrategyInfo(BaseModel):
    id: Optional[int] = None
    name: str
    description: str


mongo_sync_db = get_master_db_async()

@router.get("", response_model=List[StrategyInfo])
async def list_strategies():
    """
    List all strategies (built-in and user-uploaded).
    """
    global rows
    built_ins = [StrategyInfo(**s) for s in StrategyService.BUILT_IN_STRATEGIES]
    custom_strats = []
    if mongo_sync_db:
        # Fetch custom strategies from Postgres (if configured)
        query = "SELECT id, name, description FROM strategies"
        try:
            rows = await mongo_sync_db.fetch_all(query)
            custom_strats = [StrategyInfo(id=row["id"], name=row["name"], description=row["description"]) for row in
                             rows]
        except Exception as e:
            logging.error(f"Database error fetching strategies: {e}")
    return built_ins + custom_strats


@router.post("/upload", response_model=StrategyInfo)
async def upload_strategy(strategy: StrategyInfo):
    """
    Upload a new strategy definition (metadata only).
    Stores the strategy name and description in the database.
    """
    name = strategy.name.lower()
    # Prevent duplicates (check built-ins and existing)
    for s in StrategyService.BUILT_IN_STRATEGIES:
        if s["name"].lower() == name:
            raise HTTPException(status_code=400, detail="A built-in strategy with this name already exists.")
    if mongo_sync_db:
        # Insert into database
        try:
            query = "INSERT INTO strategies (name, description) VALUES (:name, :desc) RETURNING id, name, description"
            values = {"name": name, "desc": strategy.description}
            result = await mongo_sync_db.fetch_one(query, values)
            if result:
                return StrategyInfo(id=result["id"], name=result["name"], description=result["description"])
        except Exception as e:
            logging.error(f"Database error inserting strategy: {e}")
            raise HTTPException(status_code=500, detail="Failed to save strategy.")
    # If no database configured, or insertion failed
    raise HTTPException(status_code=500, detail="Strategy upload not supported or failed.")
