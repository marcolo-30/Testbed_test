import os
import time
import threading
from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else default


SERVICE_NAME = env("OTEL_SERVICE_NAME", "otel-test")
OTLP_GRPC_ENDPOINT = env("OTEL_EXPORTER_OTLP_ENDPOINT", "192.168.0.36:30417")  # host:port
EXPORT_INTERVAL_SEC = float(env("EXPORT_INTERVAL_SEC", "5"))
TICK_SEC = float(env("TICK_SEC", "2"))

NODE_NAME = env("K8S_NODE_NAME", env("HOSTNAME", "unknown"))

resource = Resource.create(
    {
        "service.name": SERVICE_NAME,
        "k8s.node.name": NODE_NAME,
    }
)

# Metrics (OTLP gRPC)
metric_exporter = OTLPMetricExporter(endpoint=OTLP_GRPC_ENDPOINT, insecure=True)
metric_reader = PeriodicExportingMetricReader(
    metric_exporter,
    export_interval_millis=int(EXPORT_INTERVAL_SEC * 1000),
)
metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
meter = metrics.get_meter("otel-test-meter")

counter = meter.create_counter(
    name="otel_test_counter_total",
    description="Counter that increases automatically to validate OTEL pipeline",
    unit="1",
)

# Traces (OTLP gRPC)
trace_exporter = OTLPSpanExporter(endpoint=OTLP_GRPC_ENDPOINT, insecure=True)
trace_provider = TracerProvider(resource=resource)
trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer("otel-test-tracer")


def background_emit() -> None:
    i = 0
    while True:
        counter.add(1, {"k8s.node.name": NODE_NAME})
        i += 1

        if i % 5 == 0:
            with tracer.start_as_current_span("otel_test_span") as span:
                span.set_attribute("k8s.node.name", NODE_NAME)
                span.set_attribute("iteration", i)

        time.sleep(TICK_SEC)


if __name__ == "__main__":
    print(f"[otel-test] service={SERVICE_NAME} node={NODE_NAME} otlp_grpc={OTLP_GRPC_ENDPOINT}")
    threading.Thread(target=background_emit, daemon=True).start()
    while True:
        time.sleep(60)
