

import os
import json
import uuid
import re
import heapq
import hashlib
from collections import deque
from pathlib import Path

from config import ShellConfig
from system import SystemTools
from ..time_utility import TimeUtility

def append_log(entry, path):
    """Append a JSON-serializable entry to a newline-delimited JSON file."""

    dirpath = os.path.dirname(path)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)

    try:
        text = json.dumps(entry, ensure_ascii=False)
    except (TypeError, ValueError):
        return False

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        return False

    return True


def load_schema():
    schema_path = Path(__file__).resolve().parents[2] / "ruppert_schema" / "schema.json"
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)


def _compact_text(value, limit=500):
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def build_working_entry(entry):
    """Create a lightweight labeled index of one live conversation turn."""
    conversation = entry.get("conversation") or {}
    source_id = entry.get("event_id") or _stable_record_id(entry, 0)
    facts = []
    for field, value in (
        ("conversation.call", conversation.get("call")),
        ("conversation.response", conversation.get("response")),
        ("conversation.topic", conversation.get("topic")),
        ("conversation.intent", conversation.get("intent")),
        ("user_state.mood", (entry.get("user_state") or {}).get("mood")),
        ("user_state.stress", (entry.get("user_state") or {}).get("stress")),
        ("user_state.fatigue", (entry.get("user_state") or {}).get("fatigue")),
    ):
        if value is None or value == "" or value == [] or value == {}:
            continue
        facts.append({
            "key": field,
            "value": _compact_text(value),
            "tags": _path_tags(field),
            "source_path": field,
        })
    return {
        "record_type": "conversation_turn",
        "source_record_id": source_id,
        "session_id": entry.get("session_id"),
        "timestamp": entry.get("timestamp"),
        "device_alias": (entry.get("device") or {}).get("device_alias"),
        "user": _compact_text(conversation.get("call")),
        "assistant": _compact_text(conversation.get("response")),
        "topic": _compact_text(conversation.get("topic"), limit=120),
        "intent": _compact_text(conversation.get("intent"), limit=120),
        "tags": list(conversation.get("tags") or [])[:8],
        "facts": facts,
    }


def _path_tags(path):
    tokens = re.findall(r"[A-Za-z0-9]+", str(path).replace("_", " ").replace(".", " "))
    tags = [token.casefold() for token in tokens if token]
    return list(dict.fromkeys(tags))[:16]


def _stable_record_id(record, line_number):
    try:
        content = json.dumps(
            record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=str,
        ).encode("utf-8")
    except (TypeError, ValueError):
        content = repr(record).encode("utf-8", errors="replace")
    return hashlib.sha256(str(line_number).encode("ascii") + b":" + content).hexdigest()


def iter_jsonl_records(path):
    """Yield valid JSON object records paired with their 1-based line number."""
    try:
        with Path(path).open("r", encoding="utf-8") as log_file:
            for line_number, line in enumerate(log_file, start=1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    yield line_number, record
    except OSError:
        return


def _flatten_meaningful_values(value, prefix=""):
    """Return path/value leaves, omitting empty placeholders but preserving lists."""
    if isinstance(value, dict):
        flattened = []
        for key in sorted(value):
            escaped_key = str(key).replace("~", "~0").replace("/", "~1")
            child_path = f"{prefix}/{escaped_key}"
            flattened.extend(_flatten_meaningful_values(value[key], child_path))
        return flattened
    if value is None or value == "" or value == [] or value == {}:
        return []
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return [(prefix or "/", serialized)]


def _read_jsonl(path):
    try:
        with Path(path).open("r", encoding="utf-8") as log_file:
            for line in log_file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    yield record
    except OSError:
        return


def load_prompt_context(path, query, *, recent_limit=4, match_limit=3):
    """Stream the working log and return bounded recent/relevant turns."""
    query_terms = {
        term.casefold()
        for term in re.findall(r"[\w'-]{3,}", str(query or ""))
        if term.casefold() not in {"the", "and", "for", "with", "from", "that", "this", "what", "when", "where", "how"}
    }

    recent_limit = max(0, recent_limit)
    match_limit = max(0, match_limit)
    recent = deque()
    best_matches = []
    record_count = 0

    def consider_match(index, record):
        if not query_terms or not match_limit:
            return
        fact_text = " ".join(
            " ".join(str(fact.get(key) or "") for key in ("key", "value", "source_path", "tags"))
            for fact in record.get("facts", [])
            if isinstance(fact, dict)
        )
        searchable = " ".join(
            [
                str(record.get(key) or "")
                for key in ("user", "assistant", "topic", "intent", "tags", "labels", "record_type")
            ]
            + [fact_text]
        ).casefold()
        score = sum(1 for term in query_terms if term in searchable)
        if score:
            candidate = (score, index, record)
            if len(best_matches) < match_limit:
                heapq.heappush(best_matches, candidate)
            elif candidate[:2] > best_matches[0][:2]:
                heapq.heapreplace(best_matches, candidate)

    for record in _read_jsonl(path):
        record_count += 1
        record_type = record.get("record_type", "conversation_turn")
        if record_type == "conversation_turn":
            recent.append((record_count - 1, record))
            if len(recent) > recent_limit:
                older_index, older_record = recent.popleft()
                consider_match(older_index, older_record)
        else:
            consider_match(record_count - 1, record)

    if record_count == 0:
        return None

    return {
        "recent_turns": [record for _, record in recent],
        "relevant_past_turns": [
            record for _, _, record in sorted(best_matches, reverse=True)
        ],
    }


def build_entry(adapter_output, *, session_id=None, user_message=None):
    device_config = ShellConfig()
    time_utility = TimeUtility()
    system = SystemTools()
    return {
        "event_id": str(uuid.uuid4()),
        "session_id": session_id or str(uuid.uuid4()),
        "timestamp": time_utility.now,

        "location": {
            "lat": None,
            "lon": None,
            "source": "",
            "context_location": ""
        },

        "device": {
            "device_alias": getattr(device_config, "device_alias", ""),
            "device_id": getattr(device_config, "device_id", ""),
            "device_battery": system.battery_info.get("percent", None),
            "device_plugged": system.battery_info.get("plugged", None),
            "device_secsleft": system.battery_info.get("secsleft", None),
            "device_thermal": getattr(device_config, "device_thermal", ""),
            "device_network": getattr(device_config, "device_network", ""),
            "vpn": getattr(device_config, "vpn", "")
        },

        "environment": {
            "temp": "",
            "humidity": "",
            "air_quality": "",
            "noise_level": "",
            "light_level": ""
        },

        "user_state": {
            "mood": "",
            "stress": "",
            "fatigue": "",
            "health_flags": []
        },

        "conversation": {
            "call": user_message or adapter_output["raw"].get("user_message") or adapter_output["raw"].get("prompt", ""),
            "response": adapter_output["response"],
            "topic": "",
            "intent": "",
            "tags": []
        },

        "memory": {
            "importance": 0,
            "type": "",
            "expiry": None
        },

        "model": {
            "name": adapter_output["model"],
            "version": "",
            "temperature": None,
            "tokens_in": adapter_output["tokens_in"],
            "tokens_out": adapter_output["tokens_out"],
            "latency_ms": adapter_output["latency_ms"]
        },

        "system": {
            "network_status": system.network_info.get("status", ""),
            "connected_devices": system.network_info.get("connected_devices", []),
            "pack_board_status": ""
        },

        "command": None,
        "error": adapter_output["error"],

        # Keep the complete model exchange only in the master log. The working
        # log intentionally stores a compact conversation-only projection.
        "raw": adapter_output.get("raw") or {},

        "meta": {
            "schema_version": "2.0",
            "notes": "topic, intent, tags, and user_state will be ai generated"
        }
    }