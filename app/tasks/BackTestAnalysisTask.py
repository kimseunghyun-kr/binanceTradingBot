# app/tasks/BacktestAnalysisTask.py
from app.core.celery_app import celery
from app.services.BackTestAnalysisCoordinatorService import BacktestAnalysisCoordinator

print("imported BackTestAnalysisTask")


@celery.task(bind=True)
def run_backtest_analysis_task(self, params):
    coordinator = BacktestAnalysisCoordinator(**params)
    return coordinator.run()
