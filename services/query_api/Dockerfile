# Multi-arch base image (selected automatically by buildx)
FROM python:3.9-slim

WORKDIR /app

# Ensure shared module import works
ENV PYTHONPATH="/app"

# Copy shared module
COPY shared /app/shared

# Install dependencies
COPY query_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY query_api/ /app/

# Gunicorn with Uvicorn worker; expand env var and exec for proper signals
ENTRYPOINT ["/bin/sh","-c"]
CMD ["exec gunicorn -w ${GUNICORN_WORKERS:-1} -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8002"]
