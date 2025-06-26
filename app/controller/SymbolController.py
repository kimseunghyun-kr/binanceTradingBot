from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.services.SymbolService import SymbolService

router = APIRouter(prefix="/symbols", tags=["Symbols"])

@router.get("/binance", response_model=List[str])
def get_binance_symbols():
    """
    Get all Binance symbols trading against USDT.
    """
    symbols = SymbolService.get_binance_trading_symbols()
    if not symbols:
        raise HTTPException(status_code=502, detail="Failed to fetch symbols from Binance.")
    return symbols

@router.get("/cmc", response_model=List[str])
def filter_symbols_by_cap(min_cap: float = Query(150_000_000, description="Minimum market cap (USD)"),
                          max_cap: float = Query(20_000_000_000, description="Maximum market cap (USD)"),
                          max_pages: int = Query(5, description="How many pages of CoinMarketCap data to fetch")):
    """
    Filter symbols by market cap range using CoinMarketCap data.
    Saves the filtered list and updates the global symbol list.
    """
    filtered = SymbolService.filter_symbols_by_market_cap(min_cap=min_cap, max_cap=max_cap, max_pages=max_pages)
    # After this call, symbol_utils.ANALYSIS_SYMBOLS is updated
    return filtered
