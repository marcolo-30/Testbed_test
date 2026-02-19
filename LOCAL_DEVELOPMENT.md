# Local Development Environment Guide

This document provides a complete guide to setting up and running the entire application stack (all services, Redis, OTEL Collector, and Prometheus) on your local machine using Docker Compose. This allows for development and testing when the Kubernetes cluster or other remote servers are unavailable.

## 1. Prerequisites

- **Docker Desktop:** You must have Docker Desktop installed and running on your machine. This provides the `docker` and `docker-compose` commands.

## 2. Core Concepts

- **Docker Compose:** We will use a `docker-compose.yaml` file to define and run our multi-container application. Docker Compose handles the creation of a private network for our services, allowing them to communicate using their service names as hostnames (e.g., `redis`, `otel-collector`).
- **Local Replacements:**
  - The Kubernetes cluster is replaced by Docker Compose.
  - The external Redis server is replaced by a `redis` container.
  - The external Prometheus server is replaced by a `prometheus` container.
  - The Kubernetes OTEL Collector is replaced by an `otel-collector` container.

## 3. Setup and Configuration Files

To run the local environment, you will need the following three files in the root of your project directory.

### A. `docker-compose.yaml`

This is the main file that defines all the services.

```yaml
version: '3.8'

services:
  # --- INFRASTRUCTURE ---
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    volumes:
      - ./otel-collector-local.yaml:/etc/otelcol-contrib/config.yaml
    ports:
      - "4317:4317" # OTLP gRPC
      - "9464:9464" # Prometheus Exporter

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yaml:/etc/prometheus/prometheus.yaml
    ports:
      - "9090:9090"

  # --- APPLICATION SERVICES ---
  ingest-api:
    build:
      context: .
      dockerfile: ./services/ingest_api/Dockerfile
    depends_on:
      - redis
      - otel-collector
    environment:
      - REDIS_HOST=redis
      - OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317

  process-worker:
    build:
      context: .
      dockerfile: ./services/process_worker/Dockerfile
    depends_on:
      - redis
      - otel-collector
    environment:
      - REDIS_HOST=redis
      - OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317

  query-api:
    build:
      context: .
      dockerfile: ./services/query_api/Dockerfile
    depends_on:
      - redis
      - otel-collector
    environment:
      - REDIS_HOST=redis
      - OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317

  simulator:
    build:
      context: .
      dockerfile: ./services/simulator/Dockerfile
    depends_on:
      - ingest-api
      - query-api
    environment:
      - INGEST_API_URL=http://ingest-api:8000
      - QUERY_API_URL=http://query-api:8002
      - OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317
```

### B. `prometheus.yaml`

This file tells your local Prometheus where to find the OTEL Collector.

```yaml
global:
  scrape_interval: 10s

scrape_configs:
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:9464']
```

### C. `otel-collector-local.yaml`

This file configures your local OTEL Collector.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

exporters:
  prometheus:
    endpoint: 0.0.0.0:9464
  debug:
    verbosity: detailed

processors:
  batch:

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus, debug]
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [debug]
```

## 4. How to Run the Local Environment

1.  **Create the Files:** Create the three files above (`docker-compose.yaml`, `prometheus.yaml`, `otel-collector-local.yaml`) in the root directory of your project.
2.  **Start the Environment:** Open a terminal in the root of your project and run the following command. The `--build` flag tells Docker Compose to build your application images from source before starting.

    ```sh
    docker-compose up --build
    ```

    You will see logs from all the services starting up in your terminal.

3.  **Verify It's Working:**
    - Open your browser to **`http://localhost:9090`** to access the Prometheus UI.
    - In the Prometheus query bar, you can now run the same queries as before (e.g., `rate(http_server_request_counter[1m])`). You should see data appearing.
    - The terminal running `docker-compose` will show the combined logs from all services, including the `[Worker]` logs from the `process-worker`.

## 5. How to Stop the Environment

- Press **`Ctrl+C`** in the terminal where `docker-compose` is running.
- To ensure all containers and the network are removed, run:

  ```sh
  docker-compose down
  ```

This setup provides a complete, self-contained environment for you to continue your work.
