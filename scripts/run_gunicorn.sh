#!/bin/bash
# Script to run FastAPI app with Gunicorn

# Set environment variables if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run Gunicorn
gunicorn api.app:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -


