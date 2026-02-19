# Multi-arch base image (selected automatically by buildx)
FROM python:3.9-slim

WORKDIR /app

# Ensure shared module is importable
ENV PYTHONPATH="/app"

# Copy shared module
COPY shared /app/shared

# Install dependencies
COPY simulator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY simulator/ /app/

# Run simulator
CMD ["python", "main.py"]
