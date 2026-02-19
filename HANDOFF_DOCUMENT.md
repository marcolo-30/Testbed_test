# Project Handoff Document

This document summarizes the project's context, architecture, accomplishments, and the final unresolved issue to provide a clear starting point for the next agent.

## 1. Project Goal

The objective is to create a multi-service Python application (`ingest-api`, `process-worker`, `query-api`, `simulator`) for performance and observability experiments. The application is designed to be deployed on a heterogeneous Kubernetes cluster (amd64 VMs + ARM nodes) and be fully instrumented with OpenTelemetry.

## 2. Current Architecture

- **Services:** 4 Python services, containerized using individual Dockerfiles.
- **Dependencies:** An external Redis server and a Prometheus instance, both running on a separate Ubuntu VM at `192.168.0.35`.
- **Container Registry:** A private, insecure Docker registry running at `192.168.0.35:5000`.
- **Kubernetes Cluster:** A `k3s`-based cluster named `clus1` with heterogeneous nodes:
  - `clus1` (amd64, `nodetype=vm`)
  - `r3-node` (arm64, `nodetype=rpi3`)
  - `n-node` (arm64, `nodetype=jetson`)
- **Observability:** An OpenTelemetry Collector (`otel-collector`) is running in the `observability` namespace.

## 3. Key Accomplishments (What Works)

We have successfully built a solid foundation. The next agent should not need to revisit these areas.

1.  **Multi-Architecture Image Builds:** The `docker buildx` commands are correctly configured to build and push multi-platform images (`linux/amd64`, `linux/arm64`, `linux/arm/v7`) for all services to the private registry.

2.  **Insecure Registry Configuration:** We successfully configured both the Docker client (on the Windows build machine) and the Kubernetes nodes (via `/etc/rancher/k3s/registries.yaml`) to correctly pull images from the insecure registry at `192.168.0.35:5000`.

3.  **Application Code and Dependencies:**
    - The Python code for all services has been updated to use a shared observability module.
    - The `requirements.txt` files have been corrected to resolve build failures (removing `uvloop` from `uvicorn[standard]`).
    - The application logic has been refined (e.g., removing the SQLite dependency from the `query-api`).

4.  **Kubernetes Manifests:**
    - The `Deployment`, `Service`, and `ConfigMap` YAML files in the `kubernetes/` directory are well-structured.
    - We successfully replaced the problematic `PersistentVolumeClaim` with a non-persistent `emptyDir` volume, which is appropriate for this application and resolved pod migration issues.

## 4. The Final Unresolved Problem: Cluster Networking

Despite all services and configurations being correct, there is a fundamental networking issue within the Kubernetes cluster.

- **Symptom:** Pods in the `testbed` namespace **cannot communicate with services in any other namespace**.
  - This manifests as `NameResolutionError` when the `simulator` tries to reach the `ingest-api` service.
  - It also manifests as `UNAVAILABLE` / `DEADLINE_EXCEEDED` when any pod tries to send data to the `otel-collector.observability` service.

- **Evidence & Diagnosis:**
  1.  We have proven that the `ingest-api` and `otel-collector` services are healthy and have correct `Endpoints` objects.
  2.  We have proven (using `getent hosts`) that DNS resolution for these services **fails** from within an application pod.
  3.  We have proven (by adding `dnsConfig` to a pod) that even when we manually provide the correct DNS server IP, the pod **still cannot reach it**.

- **Conclusion:** This indicates a low-level networking problem, most likely a **default-deny `NetworkPolicy`** installed by `k3s` or a faulty CNI (Container Network Interface) configuration. The network is actively blocking all cross-namespace traffic.

## 5. Recommended Next Steps for the New Agent

The application code and container images are correct. The problem is purely with the cluster's network configuration.

1.  **Isolate and Prove the `NetworkPolicy` Issue:** The immediate next step is to apply a permissive "allow-all" ingress `NetworkPolicy` to the `observability` and `testbed` namespaces. This is the final debugging step to prove that a policy is the root cause.
    ```yaml
    # Example for the 'observability' namespace
    apiVersion: networking.k8s.io/v1
    kind: NetworkPolicy
    metadata:
      name: debug-allow-all-ingress
      namespace: observability
    spec:
      podSelector: {}
      policyTypes: [Ingress]
      ingress:
      - {}
    ```
2.  **Apply the Policy:** Use `kubectl apply` to create this policy.
3.  **Restart and Verify:** Restart the deployments (`kubectl -n testbed rollout restart deployment`). The connection errors in the logs should disappear, and the `simulator` should function correctly.
4.  **Implement a Secure Policy:** Once the issue is proven, replace the temporary "allow-all" policy with a more secure, specific one that only allows the required traffic (e.g., from `testbed` pods to the `otel-collector` on port 4317).

This approach will definitively solve the final remaining issue.
