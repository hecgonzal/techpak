from .logger import build_entry as _build_entry
from .logger import append_log as _append_log
from .logger import build_working_entry, load_prompt_context
from .logger import load_schema
from config import ShellConfig
from system import SystemTools
from pathlib import Path
from datetime import datetime, timezone
import uuid

class LoggingTools:
    def __init__(self, shell_config=None):
        self.shell_config = shell_config or ShellConfig()
        self.system = SystemTools()
        legacy_path = Path(self.shell_config.log_path)
        self.master_log_path = getattr(self.shell_config, "master_log_path", None) or legacy_path
        self.working_log_path = getattr(self.shell_config, "working_log_path", None) or legacy_path.with_name("workinglog.jsonl")
        self.tech_services_log_path = getattr(self.shell_config, "tech_services_log_path", None) or legacy_path.with_name("TechServicesLog.jsonl")


    def append(self, entry):
        master_saved = self.append_master_record(entry)
        working_saved = _append_log(build_working_entry(entry), path=str(self.working_log_path))
        return master_saved and working_saved

    def append_master_record(self, record):
        """Persist a complete, policy-approved raw record without prompt compression."""
        return _append_log(record, path=str(self.master_log_path))

    def load_context(self, query, *, recent_limit=4, match_limit=3):
        return load_prompt_context(
            self.working_log_path,
            query,
            recent_limit=recent_limit,
            match_limit=match_limit,
        )

    def condense_master_log(self, *, adapter=None, max_records=100):
        """Run explicit offline condensation; normal chat never invokes the model."""
        if adapter is None:
            from adapters import load_adapter

            adapter_name = getattr(self.shell_config, "working_log_adapter", None)
            adapter_name = adapter_name or getattr(self.shell_config, "ai_model", None)
            if not adapter_name:
                raise ValueError("Configure working_log_adapter before condensing the master log")
            adapter = load_adapter(adapter_name)
        from .working_log_condensor import WorkingLogCondensor

        return WorkingLogCondensor(adapter).condense(
            self.master_log_path,
            self.working_log_path,
            max_records=max_records,
        )

    def record_service_call(
        self,
        service_name,
        *,
        operation="call",
        status="success",
        duration_ms=None,
        request_id=None,
        call_id=None,
        phase="complete",
        error=None,
    ):
        """Append service-call metadata without storing request/response payloads."""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": getattr(self.shell_config, "device_id", ""),
            "device_alias": getattr(self.shell_config, "device_alias", ""),
            "service": service_name,
            "operation": operation,
            "phase": phase,
            "status": status,
            "duration_ms": duration_ms,
            "request_id": request_id,
            "call_id": call_id or str(uuid.uuid4()),
            "error": str(error)[:300] if error else None,
        }
        return _append_log(event, path=str(self.tech_services_log_path))

    def build_entry(self, adapter_output, *, session_id=None, user_message=None):
        return _build_entry(
            adapter_output,
            session_id=session_id,
            user_message=user_message,
        )

    def load_schema(self):
        return load_schema()