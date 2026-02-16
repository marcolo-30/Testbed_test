# Production-Style Microservice Toy System for Kubernetes Experiments

This project provides a small, production-style microservice system designed for running performance and observability experiments on heterogeneous Kubernetes nodes.

## System Architecture

The system consists of four main components:

1.  **ingest-api**: A FastAPI service that receives events and writes them to an external Redis.
2.  **process-worker**: A Python service that consumes events from Redis and stores them in a persistent SQLite database.
3.  **query-api**: A FastAPI service that queries the status of an event.
4.  **simulator**: A Python application that generates load, verifies functionality, and measures downtime.

All components are instrumented with OpenTelemetry and designed to be deployed on a Kubernetes cluster with mixed-architecture nodes.

## Prerequisites

*   A running Kubernetes cluster and a configured `kubectl` CLI.
*   An external Redis instance.
*   An external Docker registry accessible from your cluster nodes.
*   An existing OpenTelemetry Collector, Prometheus, and Grafana stack.
*   **Crucially**: All cluster nodes must be configured to trust your insecure Docker registry.

## Building and Pushing Multi-Arch Images

Because the cluster contains nodes with different CPU architectures (e.g., amd64, arm64, armv7), you must build and push multi-architecture container images to your private registry.

Use `docker buildx` for this. From the root of the project, run the following commands for each service:

```sh
# Example for ingest-api
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t 192.168.0.35:5000/ingest-api:latest --push ./services/ingest_api

# Repeat for other services
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t 192.168.0.35:5000/process-worker:latest --push ./services/process_worker
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t 192.168.0.35:5000/query-api:latest --push ./services/query_api
docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t 192.168.0.35:5000/simulator:latest --push ./services/simulator
```

## Kubernetes Deployment

The following commands will deploy the entire system. They use the `karmada-apiserver` context as identified.

**PowerShell Commands:**
```powershell
# Set the KUBECONFIG environment variable for your session
$env:KUBECONFIG = "C:\Users\Maloa\.kube\config"

# 1. Create the 'testbed' namespace
kubectl --context karmada-apiserver apply -f kubernetes/namespace.yaml

# 2. Create the service endpoint for the external Redis
kubectl --context karmada-apiserver apply -f kubernetes/external-redis-service.yaml

# 3. Deploy the application ConfigMap
kubectl --context karmada-apiserver apply -f kubernetes/configmap.yaml

# 4. Deploy the applications
kubectl --context karmada-apiserver apply -f kubernetes/ingest-api.yaml
kubectl --context karmada-apiserver apply -f kubernetes/process-worker.yaml
kubectl --context karmada-apiserver apply -f kubernetes/query-api.yaml

# 5. Deploy the simulator to start the test
kubectl --context karmada-apiserver apply -f kubernetes/simulator.yaml
```

## Verifying the System

### Check Pod Status
Ensure all pods are running. Note that the `process-worker` may remain `Pending` if no `StorageClass` is available for its `PersistentVolumeClaim`.

```powershell
$env:KUBECONFIG = "C:\Users\Maloa\.kube\config"
kubectl --context karmada-apiserver get pods -n testbed -w
```

### Watch Simulator Logs
```powershell
$env:KUBECONFIG = "C:\Users\Maloa\.kube\config"
kubectl --context karmada-apiserver logs -f -l app=simulator -n testbed
```

## PromQL Examples

Use these queries in Grafana to analyze the metrics scraped from the OTEL Collector.

### P95 Latency
**Ingest API (POST /ingest):**
```promql
histogram_quantile(0.95, sum(rate(http_server_request_duration_seconds_bucket{service_name="ingest-api", http_route="/ingest"}[5m])) by (le))
```

### Error Rate (5xx)
**Ingest API:**
```promql
sum(rate(http_server_request_count_total{service_name="ingest-api", http_status_code=~"5.."}[5m])) / sum(rate(http_server_request_count_total{service_name="ingest-api"}[5m]))
```

### Downtime Rate
**Downtime by reason (health vs. functional failure):**
```promql
sum(rate(sim_downtime_seconds_total[5m])) by (target_service, reason)
```

### Worker Throughput
**Events processed per second:**
```promql
rate(worker_events_processed_total[5m])
```
