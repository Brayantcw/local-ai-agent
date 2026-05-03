import os
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

logger = logging.getLogger(__name__)


def setup_telemetry():
    """Initialize OpenTelemetry tracing."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    service_name = os.getenv("OTEL_SERVICE_NAME", "ai-agent")

    if not endpoint:
        logger.warning("OTEL_EXPORTER_OTLP_ENDPOINT not set, tracing disabled")
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    logger.info(f"OpenTelemetry configured: endpoint={endpoint}, service={service_name}")
