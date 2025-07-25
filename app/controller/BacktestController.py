"""
BacktestControllerV2.py
──────────────────────────────────────────────────────────────────────────
Enhanced backtest controller with streaming support and better architecture.
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core import celery_app
from app.core.db.mongodb_config import MongoDBConfig
from app.core.pydanticConfig.settings import get_settings
from app.core.security import get_current_user
from app.services.orchestrator.OrchestratorPoolService import orchestrator_pool
from app.tasks.BackTestTask import run_backtest_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtest V2"])
settings = get_settings()

class BacktestRequestV2(BaseModel):
    """Enhanced backtest request with custom strategy support."""
    strategy_name: str = Field(..., description="Strategy name")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Strategy parameters")
    symbols: Optional[List[str]] = Field(None, description="List of symbols to backtest")
    symbol_filter: Optional[Dict[str, Any]] = Field(None, description="Symbol filter criteria")
    interval: str = Field("1h", description="Timeframe interval")
    num_iterations: int = Field(100, description="Number of iterations")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")

    # Custom strategy
    custom_strategy_code: Optional[str] = Field(None, description="Custom strategy Python code")

    # Execution options
    use_cache: bool = Field(True, description="Use cached results")
    save_results: bool = Field(True, description="Save results to database")
    stream_progress: bool = Field(False, description="Stream progress updates")

    # Advanced options
    initial_capital: float = Field(10000.0, description="Initial capital")
    position_size_pct: float = Field(5.0, description="Position size percentage")
    max_positions: int = Field(10, description="Maximum concurrent positions")
    tp_ratio: float = Field(0.1, description="Take profit ratio")
    sl_ratio: float = Field(0.05, description="Stop loss ratio")

    # Execution model
    fee_model: Optional[Dict[str, Any]] = Field(None, description="Fee model configuration")
    slippage_model: Optional[Dict[str, Any]] = Field(None, description="Slippage model configuration")
    fill_policy: Optional[Dict[str, Any]] = Field(None, description="Fill policy configuration")


class BacktestResponse(BaseModel):
    """Response for backtest submission."""
    task_id: str
    status: str
    message: str
    websocket_url: Optional[str] = None
    pool_status: Optional[Dict[str, Any]] = None


@router.post("/submit", response_model=BacktestResponse)
async def submit_backtest(
        request: BacktestRequestV2,
        user: Dict[str, Any] = Depends(get_current_user)
) -> BacktestResponse:
    """
    Submit a new backtest with enhanced features.

    This endpoint:
    1. Validates the request
    2. Resolves symbols if using filter
    3. Submits to Celery for async execution
    4. Returns task ID and optional WebSocket URL for streaming
    """
    try:
        # Resolve symbols
        if request.symbols:
            symbols = request.symbols
        elif request.symbol_filter:
            # Use GraphQL resolver to get symbols
            from app.graphql.resolvers import SymbolResolver
            from app.graphql.types import SymbolFilter

            filter_obj = SymbolFilter(**request.symbol_filter)
            symbol_objects = await SymbolResolver.get_symbols(filter_obj, limit=100)
            symbols = [s.symbol for s in symbol_objects]
        else:
            raise HTTPException(
                status_code=400,
                detail="Either symbols or symbol_filter must be provided"
            )

        if not symbols:
            raise HTTPException(
                status_code=400,
                detail="No symbols found matching criteria"
            )

        # Prepare task payload
        task_payload = {
            "user_id": user["user_id"],
            "strategy_name": request.strategy_name,
            "strategy_params": request.strategy_params,
            "symbols": symbols,
            "interval": request.interval,
            "num_iterations": request.num_iterations,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "custom_strategy_code": request.custom_strategy_code,
            "use_cache": request.use_cache,
            "save_results": request.save_results,
            "stream_progress": request.stream_progress,
            "initial_capital": request.initial_capital,
            "position_size_pct": request.position_size_pct,
            "max_positions": request.max_positions,
            "tp_ratio": request.tp_ratio,
            "sl_ratio": request.sl_ratio,
            "fee_model": request.fee_model,
            "slippage_model": request.slippage_model,
            "fill_policy": request.fill_policy
        }

        # Submit to Celery
        async_result = run_backtest_task.delay(task_payload)

        # Get pool status
        pool_status = await orchestrator_pool.get_pool_status()

        # Prepare response
        response = BacktestResponse(
            task_id=async_result.id,
            status="submitted",
            message=f"Backtest submitted for {len(symbols)} symbols",
            pool_status=pool_status
        )

        # Add WebSocket URL if streaming requested
        if request.stream_progress:
            response.websocket_url = f"/api/v2/backtest/stream/{async_result.id}"

        return response

    except Exception as e:
        logger.error(f"Failed to submit backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_backtest_status(
        task_id: str,
        user: Dict[str, Any] = Depends(get_current_user)
):
    """Get status of a backtest task."""

    result = celery_app.AsyncResult(task_id)

    if result.state == 'PENDING':
        return {
            "task_id": task_id,
            "state": "PENDING",
            "progress": 0,
            "message": "Task is waiting in queue"
        }
    elif result.state == 'PROGRESS':
        return {
            "task_id": task_id,
            "state": "PROGRESS",
            "progress": result.info.get('progress', 0),
            "current": result.info.get('current', ''),
            "total": result.info.get('total', 0)
        }
    elif result.state == 'SUCCESS':
        return {
            "task_id": task_id,
            "state": "SUCCESS",
            "progress": 100,
            "result": result.result
        }
    elif result.state == 'FAILURE':
        return {
            "task_id": task_id,
            "state": "FAILURE",
            "error": str(result.info),
            "traceback": result.traceback
        }
    else:
        return {
            "task_id": task_id,
            "state": result.state
        }


@router.websocket("/stream/{task_id}")
async def stream_backtest_progress(
        websocket: WebSocket,
        task_id: str
):
    """
    WebSocket endpoint for streaming backtest progress.

    Sends real-time updates about:
    - Progress percentage
    - Current symbol being processed
    - Intermediate results
    - Final results
    """
    await websocket.accept()

    try:
        # Get MongoDB client
        db = MongoDBConfig.get_master_client_sync()[settings.MONGO_DB_APP]

        # Stream progress from MongoDB
        from pymongo import CursorType

        cursor = db.backtest_progress.find(
            {'task_id': task_id},
            cursor_type=CursorType.TAILABLE_AWAIT
        ).max_await_time_ms(1000)

        while True:
            try:
                async for doc in cursor:
                    # Send progress update
                    await websocket.send_json({
                        "type": "progress",
                        "data": {
                            "progress": doc.get("progress", 0),
                            "current_symbol": doc.get("current_symbol"),
                            "message": doc.get("message", ""),
                            "timestamp": doc.get("timestamp", "").isoformat() if hasattr(doc.get("timestamp"),
                                                                                         "isoformat") else str(
                                doc.get("timestamp"))
                        }
                    })

                    # Check if completed
                    if doc.get("progress", 0) >= 100:
                        # Send final result
                        result = await db.backtest_results.find_one({"task_id": task_id})
                        if result:
                            await websocket.send_json({
                                "type": "complete",
                                "data": result
                            })
                        break

                # No more documents, wait a bit
                await asyncio.sleep(0.5)

            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
    finally:
        await websocket.close()


@router.get("/results/{task_id}")
async def get_backtest_results(
        task_id: str,
        user: Dict[str, Any] = Depends(get_current_user)
):
    """Get full backtest results."""
    db = MongoDBConfig.get_master_client()[settings.MONGO_DB_APP]

    result = await db.backtest_results.find_one({"task_id": task_id})

    if not result:
        raise HTTPException(status_code=404, detail="Results not found")

    # Remove MongoDB _id field
    result.pop("_id", None)

    return result


@router.get("/pool/status")
async def get_pool_status(
        user: Dict[str, Any] = Depends(get_current_user)
):
    """Get orchestrator pool status."""
    return await orchestrator_pool.get_pool_status()


@router.post("/cancel/{task_id}")
async def cancel_backtest(
        task_id: str,
        user: Dict[str, Any] = Depends(get_current_user)
):
    """Cancel a running backtest."""

    result = celery_app.AsyncResult(task_id)
    result.revoke(terminate=True)

    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "Backtest cancellation requested"
    }


@router.get("/export/{task_id}")
async def export_backtest_results(
        task_id: str,
        format: str = "json",
        user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Export backtest results in various formats.

    Supported formats:
    - json: Raw JSON data
    - csv: CSV with trades
    - excel: Excel workbook with multiple sheets
    - pdf: PDF report
    """
    db = MongoDBConfig.get_master_client()[settings.MONGO_DB_APP]

    result = await db.backtest_results.find_one({"task_id": task_id})

    if not result:
        raise HTTPException(status_code=404, detail="Results not found")

    if format == "json":
        # Stream JSON response
        def generate():
            yield json.dumps(result, default=str, indent=2).encode()

        return StreamingResponse(
            generate(),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=backtest_{task_id}.json"
            }
        )

    elif format == "csv":
        # Convert trades to CSV
        import pandas as pd
        from io import StringIO

        trades_df = pd.DataFrame(result.get("trades", []))
        csv_buffer = StringIO()
        trades_df.to_csv(csv_buffer, index=False)

        return StreamingResponse(
            iter([csv_buffer.getvalue().encode()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=backtest_trades_{task_id}.csv"
            }
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {format}"
        )