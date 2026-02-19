# Multi-arch base image (BuildKit selects the right arch at build time)
FROM python:3.9-slim

WORKDIR /app

# Make shared module importable
ENV PYTHONPATH="/app"

# Copy shared module first (path is relative to the 'services' build context)
COPY shared /app/shared

# Install dependencies
COPY ingest_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code
COPY ingest_api/ /app/

# Use Gunicorn with Uvicorn worker. Use an entrypoint to expand env vars, then exec.
ENTRYPOINT ["/bin/sh","-c"]
CMD ["exec gunicorn -w ${GUNICORN_WORKERS:-1} -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8000"]
