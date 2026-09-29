"""Device-local service-call audit events for the tp-ruppertlog prototype."""

from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from time import perf_counter
import json
import uuid


_DEFAULT_LOG_PATH = (
    Path(__file__).resolve().parents[4]
    / "Ruppert_lite"
    / "logs"
    / "TechServicesLog.jsonl"
)


class TechServicesLog:
    """Append metadata-only records for service calls on this device."""

    def __init__(self, path=None, *, device_id="", device_alias=""):
        self.path = Path(path) if path is not None else _DEFAULT_LOG_PATH
        self.device_id = device_id
        self.device_alias = device_alias

    def record(
        self,
        service,
        operation,
        *,
        status,
        duration_ms=None,
        request_id=None,
        call_id=None,
        phase=None,
        error=None,
    ):
        event = {
            "event_id": str(uuid.uuid4()),
            "call_id": call_id or str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": self.device_id,
            "device_alias": self.device_alias,
            "service": service,
            "operation": operation,
            "phase": phase or status,
            "status": status,
            "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
            "request_id": request_id,
            "error": str(error)[:300] if error else None,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        except (OSError, TypeError, ValueError):
            # Logging must not turn a successful read-only service into a failure.
            return False
        return True


_default_log = TechServicesLog()


def service_logged(service, *, tech_services_log=None):
    """Decorate a public service entry point to record success and failure."""
    log = tech_services_log or _default_log

    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            started = perf_counter()
            request_id = kwargs.get("request_id")
            call_id = str(uuid.uuid4())
            log.record(
                service,
                function.__name__,
                status="started",
                phase="start",
                request_id=request_id,
                call_id=call_id,
            )
            try:
                result = function(*args, **kwargs)
            except Exception as error:
                log.record(
                    service,
                    function.__name__,
                    status="error",
                    phase="finish",
                    duration_ms=(perf_counter() - started) * 1000,
                    request_id=request_id,
                    call_id=call_id,
                    error=error,
                )
                raise
            log.record(
                service,
                function.__name__,
                status="success",
                phase="finish",
                duration_ms=(perf_counter() - started) * 1000,
                request_id=request_id,
                call_id=call_id,
            )
            return result

        return wrapped

    return decorate
