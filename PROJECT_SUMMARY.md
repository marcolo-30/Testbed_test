# Project Summary and Debugging Log

This document summarizes the state of the project, the architecture, the problems encountered, and the solutions implemented. It is intended to provide context for any developer or AI continuing this work.

## 1. Project Goal

The objective was to create a multi-service Python application for performance and observability experiments on a heterogeneous Kubernetes cluster (amd64 VMs, ARM-based Raspberry Pi/Jetson nodes), fully instrumented with OpenTelemetry.

## 2. Final System Architecture

- **Services:** `ingest-api`, `process-worker`, `query-api`, `simulator`.
- **Dependencies:** An external Redis and Prometheus instance running on a separate Ubuntu VM at `192.168.0.35`.
- **Container Registry:** A private, insecure Docker registry running at `192.168.0.35:5000`.
- **Kubernetes Cluster:** A `k3s`-based cluster with `clus1` (amd64), `clus2` (amd64), `r3-node` (arm64), and `n-node` (arm64).
- **Observability:** Application pods send OTEL data to a central `otel-collector` deployment.

## 3. Critical Problems and Solutions

The project involved extensive debugging. The key issues and their final solutions are documented below.

### 3.1. Core Issue: Unreliable Multi-Architecture Image Selection
- **Problem:** Pods consistently failed with `exec format error` when scheduled on ARM nodes (`r3-node`, `n-node`), even when using a multi-architecture manifest with `:latest`.
- **Diagnosis:** The `k3s` container runtime on the ARM nodes is **unreliable** at selecting the correct architecture from the manifest. It frequently pulls the `amd64` layer instead of the `arm64` layer.
- **Solution (Workaround):** The only reliable method to run on a specific architecture is to **pin the image to its specific digest**. For example, to run on an `arm64` node:
  ```yaml
  image: 192.168.0.35:5000/ingest-api:latest@sha256:<arm64-specific-digest>
  ```
- **Current State:** To achieve a stable running state, all deployments have been reverted to use the simple `:latest` tag and are being forced to run on the `clus1` (amd64) node, where architecture selection is reliable.

### 3.2. Core Issue: Persistent Storage Preventing Migration
- **Problem:** Pods using the `PersistentVolumeClaim` (`sqlite-pvc`) could not be migrated to other nodes, causing scheduling failures.
- **Diagnosis:** A `PersistentVolume` is tied to the node on which it is created. This created a scheduling conflict with the `nodeSelector` patch.
- **Solution:** The `sqlite-pvc` was removed from the deployments and replaced with a temporary `emptyDir: {}` volume. This is acceptable because the SQLite database is a cache of data in Redis.

### 3.3. Configuration and Setup Issues
- **Insecure Registry (Docker Push):** `docker buildx` failed to push to the HTTP registry.
  - **Solution:** A `buildkitd.toml` file was created to explicitly configure the builder to trust the insecure registry.

- **Insecure Registry (Kubernetes Pull):** Pods failed with `ImagePullBackOff` and `not found`.
  - **Solution:** A `registries.yaml` file was created in `/etc/rancher/k3s/` on **every node** in the cluster, and the `k3s`/`k3s-agent` service was restarted on each.

- **OpenTelemetry Collector:** The collector pod failed with `the logging exporter has been deprecated`.
  - **Solution:** The `otel-collector-config.yaml` was updated to use the modern `debug` exporter instead of `logging`. The `ConfigMap` was then deleted and re-created on both `clus1` and `clus2` to ensure a clean state.

- **Application Bug:** The `ingest-api` crashed with `NameError: name 'time' is not defined`.
  - **Solution:** Added `import time` to `services/shared/observability.py` and rebuilt all images.

## 4. Current Project Status

- **Stable State:** All four services are currently running successfully on the `clus1` (amd64) node.
- **Known Issue:** The `process-worker` and `query-api` are not generating their primary metrics (`worker_events_processed_total`, etc.), even though they are in a `Running` state.
- **Next Step:** The immediate task is to debug the `process-worker` pod running on `clus1`. The first step should be to inspect its logs for any runtime errors (e.g., Redis connection issues) that are preventing it from consuming events from the stream.

## 5. Final Commands

### To Deploy to `clus1` (Current Stable State)
```powershell
# Ensure all YAMLs use ':latest' and have no nodeSelector.
# Then, run a clean deployment.
$env:KUBECONFIG = "C:\Users\Maloa\.kube\config"
kubectl delete namespace testbed --ignore-not-found=true
Start-Sleep -Seconds 10
kubectl apply -f kubernetes/namespace.yaml
Start-Sleep -Seconds 5
kubectl apply -f kubernetes/

# Patch to force all pods to clus1
'{"spec":{"template":{"spec":{"nodeSelector":{"nodetype":"vm"}}}}}' | Out-File -FilePath ./p.json
kubectl -n testbed patch deploy ingest-api --patch-file ./p.json
kubectl -n testbed patch deploy process-worker --patch-file ./p.json
kubectl -n testbed patch deploy query-api --patch-file ./p.json
kubectl -n testbed patch deploy simulator --patch-file ./p.json
Remove-Item ./p.json
```
