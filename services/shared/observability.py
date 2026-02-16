import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

def setup_observability(service_name: str):
    """Configures OpenTelemetry for the application."""
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        SERVICE_VERSION: "0.1.0",
        "k8s.node.name": os.environ.get("NODE_NAME", "unknown"),
        "deployment.environment": os.environ.get("DEPLOYMENT_ENVIRONMENT", "development"),
    })

    # --- Tracing Setup ---
    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # --- Metrics Setup ---
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))
    )
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
