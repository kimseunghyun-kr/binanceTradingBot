# app/tasks/\BackTestTask.py
"""
Celery task for running backtests asynchronously.
Uses the sandboxed OrchestratorService to execute strategies.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from app.core.celery_app import celery
from app.services.BackTestService import BackTestServiceV2

logger = logging.getLogger(__name__)


def _extract_config(cfg: Dict[str, Any]):
    """Return typed values from the task configuration."""

    return (
        cfg.get("strategy_name"),
        cfg.get("strategy_params", {}),
        cfg.get("symbols", []),
        cfg.get("interval", "1h"),
        cfg.get("num_iterations", 100),
        cfg.get("start_date"),
        cfg.get("end_date"),
        cfg.get("custom_strategy_code"),
        cfg.get("parallel_symbols", 4),
        cfg.get("use_cache", True),
        cfg.get("save_results", True),
    )


@celery.task(name="app.tasks.BackTestTask.run_backtest_task", bind=True)
def run_backtest_task(self, config: Dict[str, Any]) -> Dict[str, Any]:
    from app.core.init_services import master_db_app_sync

    """
    Celery task to execute a backtest asynchronously.

    Args:
        config: Configuration dictionary containing:
            - strategy_name: Name of the strategy to run
            - strategy_params: Parameters for the strategy
            - symbols: List of symbols to backtest
            - interval: Timeframe interval (e.g., "1h", "4h", "1d")
            - num_iterations: Number of iterations for the backtest
            - start_date: Optional start date
            - end_date: Optional end date
            - custom_strategy_code: Optional custom strategy code
            - parallel_symbols: Number of symbols to process in parallel
            - use_cache: Whether to use caching
            - save_results: Whether to save results to database

    Returns:
        Dictionary with backtest results summary
    """
    task_id = self.request.id
    logger.info(f"Starting backtest task {task_id} with config: {config}")

    try:
        # Update task progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Initializing backtest...'}
        )

        # Extract configuration
        (
            strategy_name,
            strategy_params,
            symbols,
            interval,
            num_iterations,
            start_date,
            end_date,
            custom_strategy_code,
            parallel_symbols,
            use_cache,
            save_results,
        ) = _extract_config(config)

        # Validate inputs
        if not strategy_name and not custom_strategy_code:
            raise ValueError("Either strategy_name or custom_strategy_code must be provided")

        if not symbols:
            raise ValueError("At least one symbol must be provided")

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 10, 'total': 100, 'status': 'Running backtest...'}
        )

        # Run backtest using the service
        with asyncio.Runner() as runner:
            result = runner.run(BackTestServiceV2.run_backtest(
                strategy_name=strategy_name,
                strategy_params=strategy_params,
                symbols=symbols,
                interval=interval,
                num_iterations=num_iterations,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat()  if end_date   else None,
                custom_strategy_code=custom_strategy_code,
                parallel_symbols=parallel_symbols,
                use_cache=use_cache,
                save_results=save_results
            ))

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': 'Finalizing results...'}
        )

        # Store task result reference
        if save_results:
            try:
                db = master_db_app_sync()
                task_doc = {
                    "task_id": task_id,
                    "type": "backtest",
                    "config": config,
                    "result_id": result.get("id"),
                    "status": "completed",
                    "created_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow()
                }
                db.tasks.insert_one(task_doc)
            except Exception as e:
                logger.error(f"Failed to save task reference: {e}")

        # Return summary for Celery result
        summary = {
            "task_id": task_id,
            "status": "completed",
            "result_id": result.get("id"),
            "total_trades": len(result.get("trades", [])),
            "win_rate": result.get("win_rate"),
            "total_return": result.get("total_return"),
            "sharpe_ratio": result.get("sharpe_ratio"),
            "max_drawdown": result.get("max_drawdown"),
            "execution_time": result.get("execution_time_seconds")
        }

        logger.info(f"Backtest task {task_id} completed successfully")
        return summary

    except Exception as e:
        logger.error(f"Backtest task {task_id} failed: {e}")

        # Update task state
        self.update_state(
            state='FAILURE',
            meta={'exc_type': type(e).__name__, 'exc_message': str(e)}
        )

        # Store failure in database
        try:
            db = master_db_app_sync()
            task_doc = {
                "task_id": task_id,
                "type": "backtest",
                "config": config,
                "status": "failed",
                "error": str(e),
                "created_at": datetime.utcnow(),
                "failed_at": datetime.utcnow()
            }
            db.tasks.insert_one(task_doc)
        except Exception as db_error:
            logger.error(f"Failed to save task error: {db_error}")

        raise


@celery.task(name="app.tasks.BackTestTask.get_task_status")
def get_task_status(task_id: str) -> Dict[str, Any]:
    from app.core.init_services import master_db_app_sync

    """
    Get the status of a backtest task.

    Args:
        task_id: The Celery task ID

    Returns:
        Dictionary with task status and metadata
    """
    try:
        # Get task from Celery
        task = celery.AsyncResult(task_id)

        # Get additional info from database
        db = master_db_app_sync()
        task_doc = db.tasks.find_one({"task_id": task_id})

        status_info = {
            "task_id": task_id,
            "state": task.state,
            "info": task.info if task.state != 'PENDING' else None,
            "result": task.result if task.state == 'SUCCESS' else None,
            "created_at": task_doc.get("created_at") if task_doc else None,
            "completed_at": task_doc.get("completed_at") if task_doc else None
        }

        return status_info

    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        return {
            "task_id": task_id,
            "state": "ERROR",
            "error": str(e)
        }


@celery.task(name="app.tasks.BackTestTask.cleanup_old_tasks")
def cleanup_old_tasks(days: int = 30) -> Dict[str, int]:
    from app.core.init_services import master_db_app_sync

    """
    Clean up old task records from the database.

    Args:
        days: Number of days to keep task records

    Returns:
        Dictionary with cleanup statistics
    """
    try:
        db = master_db_app_sync()
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Delete old task records
        result = db.tasks.delete_many({
            "created_at": {"$lt": cutoff_date}
        })

        # Also clean up old backtest results if needed
        backtest_result = db.backtest_results.delete_many({
            "created_at": {"$lt": cutoff_date}
        })

        stats = {
            "tasks_deleted": result.deleted_count,
            "backtest_results_deleted": backtest_result.deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }

        logger.info(f"Cleanup completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise