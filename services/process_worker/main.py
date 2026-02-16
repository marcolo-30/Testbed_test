import os
import json
import time
import sqlite3
import threading
from fastapi import FastAPI, Response
import redis
from shared.observability import setup_observability, busy_wait
from opentelemetry.metrics import Observation

# --- Configuration ---
SERVICE_NAME = os.environ.get("SERVICE_NAME", "process-worker")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
DB_PATH = os.environ.get("DB_PATH", "events.db")
CPU_WORK_MS = int(os.environ.get("CPU_WORK_MS", 0))

# --- Observability ---
tracer, meter = setup_observability(SERVICE_NAME)

# --- State for Gauges ---
db_dependency_state = {"up": 0}

# --- Metrics ---
worker_events_consumed = meter.create_counter("worker.events.consumed")
worker_events_processed = meter.create_counter("worker.events.processed")
worker_event_processing_duration = meter.create_histogram("worker.event.processing.duration", unit="s")
worker_loop_errors = meter.create_counter("worker.loop.errors")

def db_health_callback(result):
    yield Observation(db_dependency_state["up"], {"dependency": "sqlite"})

meter.create_observable_gauge(
    "app.dependencies.up",
    callbacks=[db_health_callback],
    description="Status of application dependencies (1 for up, 0 for down)",
)

# --- Database ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT,
                device_id TEXT,
                value REAL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

# --- Worker Logic ---
def process_events():
    redis_client = redis.Redis(host=REDIS_HOST, port=6379)
    group_name = "processing_group"
    consumer_name = f"consumer-{os.getpid()}"

    try:
        redis_client.xgroup_create("events_stream", group_name, id="0", mkstream=True)
    except redis.exceptions.ResponseError as e:
        if "already exists" not in str(e):
            raise

    while True:
        try:
            messages = redis_client.xreadgroup(
                group_name, consumer_name, {"events_stream": ">"}, count=1, block=1000
            )
            if not messages:
                continue

            worker_events_consumed.add(1)
            start_time = time.time()

            stream, msg_list = messages[0]
            msg_id, data = msg_list[0]
            event_data = json.loads(data[b"data"])

            if CPU_WORK_MS > 0:
                busy_wait(CPU_WORK_MS)

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO processed_events (event_id, timestamp, device_id, value) VALUES (?, ?, ?, ?)",
                    (event_data["event_id"], event_data["timestamp"], event_data["device_id"], event_data["value"])
                )
                conn.commit()

            redis_client.xack("events_stream", group_name, msg_id)
            worker_events_processed.add(1)
            worker_event_processing_duration.record(time.time() - start_time)

        except Exception as e:
            worker_loop_errors.add(1)
            print(f"Error processing event: {e}")
            time.sleep(1)

# --- Health Check Server ---
app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/ready")
def readiness_check(response: Response):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("SELECT 1")
        db_dependency_state["up"] = 1
        return {"status": "ok"}
    except Exception:
        db_dependency_state["up"] = 0
        response.status_code = 503
        return {"status": "error", "details": "Database not reachable"}


if __name__ == "__main__":
    init_db()
    worker_thread = threading.Thread(target=process_events, daemon=True)
    worker_thread.start()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
