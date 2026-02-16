# Testbed Environment Configuration

This document outlines the components and network configuration of the experimental testbed.

## 1. External Services VMs

### Karmada Control Plane VM
- **VM Hostname:** `cloudvm`
- **VM IP Address:** `192.168.0.18`
- **Services Hosted:** Karmada

### Infrastructure Services VM
- **VM Hostname:** `ubuntu`
- **VM IP Address:** `192.168.0.35`

#### Services Hosted (Docker Containers):
- **Prometheus:**
  - **Container Name:** `prometheus`
  - **Image:** `prom/prometheus:latest`
  - **Access URL:** `http://192.168.0.35:9090`
- **Grafana:**
  - **Container Name:** `grafana`
  - **Image:** `grafana/grafana:10.2.3`
  - **Access URL:** `http://192.168.0.35:3000`
- **Envoy Proxy:**
  - **Container Name:** `iot-envoy`
  - **Image:** `envoyproxy/envoy:v1.30-latest`
  - **Listener Ports:** `8080`, `9901`
- **Docker Registry:**
  - **Container Name:** `registry`
  - **Image:** `registry:2`
  - **Registry URL:** `192.168.0.35:5000`
  - **Notes:** Used to push and pull container images for the Kubernetes cluster.
- **Redis:**
  - **Container Name:** `redis`
  - **Image:** `redis:7-alpine`
  - **Access Port:** `6379`

---

## 2. Kubernetes Cluster (Testbed)

This is the primary environment for running the microservice experiments.

### Cluster Nodes:
- **Node 1 (Control Plane/Worker):**
  - **Hostname:** `clus1`
  - **IP Address:** `192.168.0.36`
  - **Type/Architecture:** `VM ubuntu`
- **Node 2 (Worker):**
  - **Hostname:** `r3-node`
  - **IP Address:** `192.168.0.15`
  - **Type/Architecture:** `Raspberry Pi 3, armv7`
- **Node 3 (Worker):**
  - **Hostname:** `n-node`
  - **IP Address:** `192.168.0.28`
  - **Type/Architecture:** `Jetson Nano, arm64`
- **Node 4 (Control Plane/Worker):**
  - **Hostname:** `clus2`
  - **IP Address:** `192.168.0.14`
  - **Type/Architecture:** `VM ubuntu`
- **Node 5 (Worker):**
  - **Hostname:** `r-node`
  - **IP Address:** `192.168.0.16`
  - **Type/Architecture:** `Raspberry Pi 4, armv7`

### Existing Observability Services (in `observability` namespace)

- **OpenTelemetry Collector:**
  - **Pod Name:** `otel-collector-7878874bbd-g4slt`
  - **Service Name:** `otel-collector` (Verified)
  - **Service URL (within cluster):** `http://otel-collector.observability.svc.cluster.local:4317` (for OTLP gRPC)
  - **Notes:** This is the central collector that receives OTLP data from the application pods.

- **OpenTelemetry Node Agents (DaemonSet):**
  - **Purpose:** Collects host-level metrics from each node.
  - **Pod Names:** `otel-node-agent-5xvzl`, `otel-node-agent-h229s`, `otel-node-agent-v5vnb`
  - **Notes:** These agents run on each node (`r3-node`, `clus1`, `n-node`).
