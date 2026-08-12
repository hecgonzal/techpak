import uuid
from ..time_utility import now
from config.shell_config import ShellConfig
from system.battery import get_battery_info

def build_entry(adapter_output):
    device = ShellConfig()
    battery_info = get_battery_info()

    return {
        "session_id": str(uuid.uuid4()),
        "timestamp": now,

        "location": {
            "lat": None,
            "lon": None,
            "source": "",
            "context_location": ""
        },

        "device": {
            "device_alias": getattr(device, "device_alias", ""),
            "device_id": getattr(device, "device_id", ""),
            "device_battery": battery_info.get("percent", None),
            "device_plugged": battery_info.get("plugged", None),
            "device_secsleft": battery_info.get("secsleft", None),
            "device_thermal": getattr(device, "device_thermal", ""),
            "device_network": getattr(device, "device_network", ""),
            "vpn": getattr(device, "vpn", "")
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
            "network_status": "",
            "connected_devices": [],
            "pack_board_status": ""
        },

        "command": None,
        "error": adapter_output["error"],

        "meta": {
            "schema_version": "2.0",
            "notes": "topic, intent, tags, and user_state will be ai generated"
        }
    }