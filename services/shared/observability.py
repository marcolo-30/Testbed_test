import os
import time
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Use the gRPC exporters to match the working otel-test service
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter


def setup_observability(service_name: str):
    """Configures OpenTelemetry for the application, matching the otel-test setup."""
    
    # Get the OTLP endpoint from the environment variable
    otlp_grpc_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        SERVICE_VERSION: "0.1.0",
        "k8s.node.name": os.environ.get("NODE_NAME", "unknown"),
        "deployment.environment": os.environ.get("DEPLOYMENT_ENVIRONMENT", "development"),
    })

    # --- Tracing Setup (gRPC, insecure) ---
    trace_exporter = OTLPSpanExporter(endpoint=otlp_grpc_endpoint, insecure=True)
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # --- Metrics Setup (gRPC, insecure) ---
    metric_exporter = OTLPMetricExporter(endpoint=otlp_grpc_endpoint, insecure=True)
    metric_reader = PeriodicExportingMetricReader(metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    return trace.get_tracer(service_name), metrics.get_meter(service_name)


def busy_wait(milliseconds: int):
    """A simple busy-wait loop to simulate CPU work."""
    if milliseconds <= 0:
        return
    end_time = time.monotonic() + milliseconds / 1000.0
    while time.monotonic() < end_time:
        pass
