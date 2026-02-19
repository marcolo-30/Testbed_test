# Analysis and Plan: Aligning Services with otel-test

## 1. Executive Summary

The user has correctly identified that the `otel-test` service successfully sends data to the collector, while the other services (`ingest-api`, etc.) fail with `UNAVAILABLE` / `DEADLINE_EXCEEDED` errors.

My previous analysis was incorrect. The services are **not** configured identically. The key difference is **how they connect to the OpenTelemetry Collector.**

- **`otel-test`:** Connects **directly to a Node IP and NodePort** (`192.168.0.36:30417`). This bypasses most of Kubernetes' internal networking and network policies.
- **Other Services:** Attempt to connect using the proper **Kubernetes Service DNS name** (`otel-collector.observability.svc.cluster.local:4317`). This connection is being blocked, almost certainly by a `NetworkPolicy`.

The success of `otel-test` is misleading; it works precisely because it *avoids* the Kubernetes networking layer that is blocking the other services.

## 2. Detailed Comparison

| Feature | `otel-test` (Working) | `ingest-api`, `query-api`, etc. (Failing) |
| :--- | :--- | :--- |
| **Configuration Method** | Environment variable with a **hardcoded default value** in `main.py`. | Environment variable loaded from the `app-config` **ConfigMap**. |
| **OTEL Endpoint Used** | `192.168.0.36:30417` (A specific Node's IP and a NodePort) | `otel-collector.observability.svc.cluster.local:4317` (Internal Service DNS) |
| **Network Path** | Pod -> Node Network -> NodePort Service -> Collector Pod | Pod -> Cluster DNS -> ClusterIP Service -> **(BLOCKED HERE)** -> Collector Pod |
| **Protocol** | gRPC | gRPC |
| **Security** | `insecure=True` | `insecure=True` |

## 3. The Root Cause

The `UNAVAILABLE` error is happening because a **Kubernetes Network Policy** is blocking TCP traffic from pods in the `testbed` namespace to pods in the `observability` namespace.

`otel-test` works by coincidence because its hardcoded `NodePort` connection does not traverse this blocked internal network path. The other services are failing because they are correctly trying to use the internal service DNS, which *is* subject to these policies.

## 4. The Plan Forward

We have two options to achieve a working state. Option A is the correct, long-term solution. Option B is a workaround that mimics the behavior of `otel-test`.

### Option A: Fix the Network (Recommended)

This is the correct, Kubernetes-native solution. We will fix the networking issue that is blocking the proper service-to-service communication.

1.  **Apply a Permissive Network Policy:** Apply the `allow-all-ingress.yaml` policy to the `observability` namespace. This is a temporary debugging step to prove that a policy is the root cause.
2.  **Verify Connection:** Restart the application pods. The `UNAVAILABLE` error will disappear, confirming the diagnosis.
3.  **Apply a Secure Policy (Optional but Recommended):** Replace the "allow-all" policy with the more specific `otel-collector-netpol.yaml` policy that only allows the required traffic.

### Option B: Revert to NodePort (Workaround)

This approach makes all services behave like `otel-test`. It will work, but it is brittle and not standard practice.

1.  **Find the NodePort:** Run `kubectl -n observability get svc otel-collector` to find the NodePort mapped to port 4317 (e.g., `30417`).
2.  **Find a Node IP:** Get the IP of a reliable node, like `clus1` (`192.168.0.36`).
3.  **Update the ConfigMap:** Change the `OTEL_EXPORTER_OTLP_ENDPOINT` in `configmap.yaml` to `http://192.168.0.36:30417`.
4.  **Redeploy:** Restart all application pods. They will now connect directly, bypassing the network policy.

**Recommendation:** I strongly recommend **Option A**. It fixes the underlying problem and results in a more robust and portable system. Please let me know which option you would like to proceed with.
