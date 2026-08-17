

import os
import json
import uuid

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
    with open("schema/schema.json") as f:
        return json.load(f)


def build_entry(adapter_output):
    device_config = ShellConfig()
    time_utility = TimeUtility()
    system = SystemTools()
    return {
        "session_id": str(uuid.uuid4()),
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
            "call": adapter_output["raw"].get("prompt", ""),
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

        "meta": {
            "schema_version": "2.0",
            "notes": "topic, intent, tags, and user_state will be ai generated"
        }
    }