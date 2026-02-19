import os
import time
from fastapi import FastAPI, Request, Response
import redis
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import Observation

from shared.observability import setup_observability, busy_wait

# --- Configuration ---
SERVICE_NAME = os.environ.get("SERVICE_NAME", "query-api")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
CPU_WORK_MS = int(os.environ.get("CPU_WORK_MS", 0))

# --- Observability ---
tracer, meter = setup_observability(SERVICE_NAME)

# --- State for Gauges ---
redis_dependency_state = {"up": 0}

# --- Metrics ---
http_server_request_counter = meter.create_counter("http.server.request.count")
http_server_request_duration = meter.create_histogram("http.server.request.duration", unit="s")

def redis_health_callback(result):
    yield Observation(redis_dependency_state["up"], {"dependency": "redis"})

meter.create_observable_gauge(
    "app.dependencies.up",
    callbacks=[redis_health_callback],
    description="Status of application dependencies (1 for up, 0 for down)",
)

# --- Application ---
app = FastAPI()
redis_client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)


@app.middleware("http")
async def otel_metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    route = request.scope.get("route")
    route_template = route.path_format if route else "unknown"

    http_server_request_counter.add(1, {
        "service": SERVICE_NAME,
        "http.route": route_template,
        "http.request.method": request.method,
        "http.response.status_code": response.status_code,
    })
    http_server_request_duration.record(duration, {
        "service": SERVICE_NAME,
        "http.route": route_template,
        "http.request.method": request.method,
        "http.response.status_code": response.status_code,
    })
    return response


@app.get("/status/{event_id}")
def get_status(event_id: str):
    with tracer.start_as_current_span("get_status"):
        if CPU_WORK_MS > 0:
            busy_wait(CPU_WORK_MS)

        # Simplified logic: Check for a status key in Redis
        status = redis_client.get(f"event_status:{event_id}")
        if status:
            return {"status": status}
        else:
            # If no status key, assume it's been received but not yet processed
            return {"status": "received"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ready")
def readiness_check(response: Response):
    try:
        redis_ok = redis_client.ping()
        if redis_ok:
            redis_dependency_state["up"] = 1
            return {"status": "ok"}
        else:
            redis_dependency_state["up"] = 0
            response.status_code = 503
            return {"status": "error", "details": "Redis not reachable"}
    except Exception:
        redis_dependency_state["up"] = 0
        response.status_code = 503
        return {"status": "error", "details": "Redis not reachable"}


# Instrument FastAPI - no tracer_provider needed if a global one is set
FastAPIInstrumentor.instrument_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
