from app.core.celery_app import celery
import logging
from datetime import datetime

from app.core.db import mongo_sync_db
from app.services.analysisService import AnalysisService


@celery.task(name="app.tasks.analysis.run_analysis_task")
def run_analysis_task(config: dict):
    """
    Celery task to perform market analysis on given symbols and interval.
    Logs and (optionally) stores the summary of signals.
    """
    interval = config.get("interval", "1d")
    symbols = config.get("symbols", [])
    yes_signals, no_count = AnalysisService.analyze_symbols(symbols, interval=interval)
    # Prepare summary log
    logging.info(f"=== Analysis Results ({interval}) ===")
    if yes_signals:
        logging.info(f"🚨 Buy signals: {', '.join(yes_signals)}")
    else:
        logging.info("✅ No buy signals detected.")
    logging.info(f"Total symbols analyzed: {len(symbols)}, Buy signals: {len(yes_signals)}, No signals: {no_count}")
    # Optionally store the analysis result in DB (e.g., in Mongo for history)
    if mongo_sync_db:
        try:
            mongo_sync_db["analysis_results"].insert_one({
                "interval": interval,
                "run_at": datetime.utcnow(),
                "buy_signals": yes_signals,
                "no_signal_count": no_count,
                "total_symbols": len(symbols)
            })
        except Exception as e:
            print(f"[AnalysisTask] MongoDB insert failed: {e}")
    # Return a brief result
    return {"buy_signals": yes_signals, "no_signals": no_count, "total": len(symbols)}
