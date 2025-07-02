FROM python:3.9-slim

WORKDIR /orchestrator

# Install any OS dependencies you need (e.g., for pandas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy orchestrator requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy orchestrator source code (including strategies, repo, etc.)
COPY . .

# Entrypoint for orchestrator (could be StrategyOrchestrator.py, or main.py)
CMD ["python", "StrategyOrchestrator.py"]
