# Use a multi-arch base image
FROM --platform=$BUILDPLATFORM python:3.9-slim

WORKDIR /app

# Add shared module to PYTHONPATH
ENV PYTHONPATH "${PYTHONPATH}:/app"

# Copy shared module first (path is relative to the 'services' build context)
COPY shared /app/shared

# Copy requirements and install (path is relative to the 'services' build context)
COPY query_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code (path is relative to the 'services' build context)
COPY query_api/ .

# Use Gunicorn for production. Use shell form to allow env var expansion.
CMD exec gunicorn -w ${GUNICORN_WORKERS:-1} -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8002
