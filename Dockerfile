# File: Dockerfile
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install OS dependencies (if any, e.g., for numpy/pandas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .
# Create a user and group named 'celery'
RUN groupadd -r celery && useradd -r -g celery celery

RUN chown -R celery:celery /app

# Expose port 8000 for FastAPI
EXPOSE 8000

# Switch to non-root user for runtime
USER celery

# Default command (can be overridden in docker-compose for worker)
CMD ["uvicorn", "KwontBot:app", "--host", "0.0.0.0", "--port", "8000"]
