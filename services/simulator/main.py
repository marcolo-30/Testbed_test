import os
import time
import datetime
import uuid
import threading
import requests
from concurrent.futures import ThreadPoolExecutor

# Assuming 'shared' is in the python path
from shared.observability import setup_observability

# --- Configuration ---
SERVICE_NAME = os.environ.get("SERVICE_NAME", "simulator")
INGEST_API_URL = os.environ.get("INGEST_API_URL", "http://localhost:8000")
QUERY_API_URL = os.environ.get("QUERY_API_URL", "http://localhost:8002")
SIM_DURATION_SECONDS = int(os.environ.get("SIM_DURATION_SECONDS", 60))
SIM_INGEST_RPS = int(os.environ.get("SIM_INGEST_RPS", 5))
SIM_POLL_INTERVAL_SECONDS = float(os.environ.get("SIM_POLL_INTERVAL_SECONDS", 0.5))
SIM_POLL_TIMEOUT_SECONDS = float(os.environ.get("SIM_POLL_TIMEOUT_SECONDS", 10))
SIM_HEALTH_TIMEOUT_SECONDS = float(os.environ.get("SIM_HEALTH_TIMEOUT_SECONDS", 2))
HEALTH_CHECK_INTERVAL_SECONDS = 5

# --- Observability ---
tracer, meter = setup_observability(SERVICE_NAME)

# --- Metrics ---
sim_client_request_count = meter.create_counter(
    "sim.client.request.count",
    description="Total count of client-side requests."
)
sim_client_request_duration = meter.create_histogram(
    "sim.client.request.duration",
    unit="s",
    description="Client-side perceived request duration."
)
sim_downtime_seconds = meter.create_counter(
    "sim.downtime.seconds",
    unit="s",
    description="Total seconds of perceived downtime."
)
sim_inflight_tests = meter.create_up_down_counter(
    "sim.inflight.tests",
    description="Number of in-flight functional smoke tests."
)

# --- State for Downtime Calculation ---
downtime_tracker = {
    "ingest-api": {"up": True, "since": time.time()},
    "query-api": {"up": True, "since": time.time()},
    "functional": {"up": True, "since": time.time()}
}
downtime_lock = threading.Lock()

def record_downtime(service: str, is_down: bool):
    with downtime_lock:
        state = downtime_tracker[service]
        if is_down and state["up"]:
            # Transition to DOWN
            state["up"] = False
            state["since"] = time.time()
            print(f"DOWNTIME DETECTED for {service}")
        elif not is_down and not state["up"]:
            # Transition to UP
            duration = time.time() - state["since"]
            reason = "health_fail" if service != "functional" else "functional_fail"
            sim_downtime_seconds.add(duration, {"target_service": service, "reason": reason})
            state["up"] = True
            state["since"] = time.time()
            print(f"DOWNTIME RECOVERED for {service} after {duration:.2f}s")

def instrumented_request(method, url, target_service, endpoint, **kwargs):
    start_time = time.time()
    result = "ok"
    try:
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout:
        result = "timeout"
        raise
    except requests.exceptions.RequestException:
        result = "error"
        raise
    finally:
        duration = time.time() - start_time
        sim_client_request_count.add(1, {
            "target_service": target_service,
            "endpoint": endpoint,
            "result": result
        })
        sim_client_request_duration.record(duration, {
            "target_service": target_service,
            "endpoint": endpoint
        })

def run_health_checks(stop_event: threading.Event):
    """Periodically checks the health of dependent services."""
    while not stop_event.is_set():
        # Check Ingest API
        try:
            instrumented_request("GET", f"{INGEST_API_URL}/health", "ingest-api", "/health", timeout=SIM_HEALTH_TIMEOUT_SECONDS)
            record_downtime("ingest-api", is_down=False)
        except Exception:
            record_downtime("ingest-api", is_down=True)

        # Check Query API
        try:
            instrumented_request("GET", f"{QUERY_API_URL}/health", "query-api", "/health", timeout=SIM_HEALTH_TIMEOUT_SECONDS)
            record_downtime("query-api", is_down=False)
        except Exception:
            record_downtime("query-api", is_down=True)

        time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

def functional_test_worker():
    """Represents a single user journey: ingest -> poll until processed."""
    sim_inflight_tests.add(1)
    test_start_time = time.time()
    event_id = None
    try:
        # 1. Ingest event
        payload = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "device_id": f"device_{uuid.uuid4()}",
            "value": 123.45
        }
        response = instrumented_request("POST", f"{INGEST_API_URL}/ingest", "ingest-api", "/ingest", json=payload, timeout=5)
        event_id = response.json()["event_id"]

        # 2. Poll for status
        poll_deadline = time.time() + SIM_POLL_TIMEOUT_SECONDS
        while time.time() < poll_deadline:
            try:
                status_response = instrumented_request("GET", f"{QUERY_API_URL}/status/{event_id}", "query-api", "/status/{event_id}", timeout=2)
                status = status_response.json().get("status")
                if status == "processed":
                    record_downtime("functional", is_down=False)
                    return # Success
            except Exception:
                # Ignore individual poll errors, rely on timeout
                pass
            time.sleep(SIM_POLL_INTERVAL_SECONDS)

        # 3. If we reach here, it's a timeout
        print(f"Functional test TIMEOUT for event {event_id}")
        record_downtime("functional", is_down=True)

    except Exception as e:
        print(f"Functional test FAILED: {e}")
        record_downtime("functional", is_down=True)
    finally:
        sim_inflight_tests.add(-1)


def main():
    print("--- Starting Simulator ---")
    print(f"Duration: {SIM_DURATION_SECONDS}s, RPS: {SIM_INGEST_RPS}")
    print(f"Ingest API: {INGEST_API_URL}, Query API: {QUERY_API_URL}")

    stop_event = threading.Event()
    health_thread = threading.Thread(target=run_health_checks, args=(stop_event,), daemon=True)
    health_thread.start()

    executor = ThreadPoolExecutor(max_workers=SIM_INGEST_RPS * 2)
    simulation_end_time = time.time() + SIM_DURATION_SECONDS
    
    print("Simulation running...")
    while time.time() < simulation_end_time:
        start_of_second = time.time()
        for _ in range(SIM_INGEST_RPS):
            executor.submit(functional_test_worker)
        
        # Maintain RPS rate
        elapsed = time.time() - start_of_second
        sleep_time = max(0, 1.0 - elapsed)
        time.sleep(sleep_time)

    print("Simulation duration ended. Shutting down...")
    stop_event.set()
    executor.shutdown(wait=True)
    # Final flush of any ongoing downtime
    record_downtime("ingest-api", is_down=False)
    record_downtime("query-api", is_down=False)
    record_downtime("functional", is_down=False)
    print("Simulator finished.")


if __name__ == "__main__":
    main()
