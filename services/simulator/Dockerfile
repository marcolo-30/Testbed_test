# Use a multi-arch base image
FROM --platform=$BUILDPLATFORM python:3.9-slim

WORKDIR /app

# Add shared module to PYTHONPATH
ENV PYTHONPATH "${PYTHONPATH}:/app"

# Copy shared module first (path is relative to the 'services' build context)
COPY shared /app/shared

# Copy requirements and install (path is relative to the 'services' build context)
COPY simulator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code (path is relative to the 'services' build context)
COPY simulator/ .

CMD ["python", "main.py"]
