# strategyOrchestrator/Dockerfile
FROM python:3.12-slim

WORKDIR /orchestrator

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# requirements live under strategyOrchestrator/
COPY strategyOrchestrator/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# bring in settings so `app.core.pydanticConfig.settings` can import
RUN mkdir -p app/core/pydanticConfig
COPY app/core/pydanticConfig/settings.py app/core/pydanticConfig/settings.py

# ⬇️ copy the *package directory* intact
COPY strategyOrchestrator /orchestrator/strategyOrchestrator

# (optional but recommended) ensure it's a proper package
# make sure these exist in your repo:
#   strategyOrchestrator/__init__.py
#   strategyOrchestrator/entities/__init__.py
#   ...

ENV PYTHONPATH=/orchestrator
CMD ["python", "-m", "strategyOrchestrator.StrategyOrchestrator"]
