# app/tasks/GridSearchTask.py

from app.services.GridSearchService import GridSearchService
from app.core.celery_app import celery

@celery.task(bind=True)
def run_grid_search_task(self, params):
    return GridSearchService.run_grid_search(**params)