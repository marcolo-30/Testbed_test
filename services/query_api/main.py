import os
import sqlite3
import time
from fastapi import FastAPI, Request, Response
import redis
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import Observation

from shared.observability import setup_observability, busy_wait

# --- Configuration ---
SERVICE_NAME = os.environ.get("SERVICE_NAME", "query-api")
DB_PATH = os.environ.get("DB_PATH", "events.db")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
CPU_WORK_MS = int(os.environ.get("CPU_WORK_MS", 0))

# --- Observability ---
tracer, meter = setup_observability(SERVICE_NAME)

# --- State for Gauges ---
db_dependency_state = {"up": 0}
redis_dependency_state = {"up": 0}

# --- Metrics ---
http_server_request_counter = meter.create_counter("http.server.request.count")
http_server_request_duration = meter.create_histogram("http.server.request.duration", unit="s")

def db_health_callback(result):
    yield Observation(db_dependency_state["up"], {"dependency": "sqlite"})

def redis_health_callback(result):
    yield Observation(redis_dependency_state["up"], {"dependency": "redis"})

meter.create_observable_gauge(
    "app.dependencies.up",
    callbacks=[db_health_callback, redis_health_callback],
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

        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT event_id FROM processed_events WHERE event_id = ?", (event_id,))
                result = cursor.fetchone()
                if result:
                    return {"status": "processed"}
        except sqlite3.OperationalError:
            # Handle cases where the DB might be locked or unavailable
            return {"status": "unknown"}


        # Check if the event is still in Redis (or recently ingested)
        # This is a simplification; a real system might need a more robust check.
        # For this toy system, we assume if it's not in SQLite, it's either received or missing.
        # A simple check against a recent cache or a bloom filter could work here.
        # For now, we'll just say "received" if not in DB.
        return {"status": "received"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ready")
def readiness_check(response: Response):
    db_ok = False
    redis_ok = False

    try:
        with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
            conn.execute("SELECT 1")
        db_ok = True
        db_dependency_state["up"] = 1
    except Exception:
        db_dependency_state["up"] = 0
        response.status_code = 503
        return {"status": "error", "details": "Database not reachable"}

    try:
        redis_ok = redis_client.ping()
        if redis_ok:
            redis_dependency_state["up"] = 1
        else:
            redis_dependency_state["up"] = 0
            response.status_code = 503
            return {"status": "error", "details": "Redis not reachable"}
    except Exception:
        redis_dependency_state["up"] = 0
        response.status_code = 503
        return {"status": "error", "details": "Redis not reachable"}

    if db_ok and redis_ok:
        return {"status": "ok"}


# Instrument FastAPI - no tracer_provider needed if a global one is set
FastAPIInstrumentor.instrument_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
