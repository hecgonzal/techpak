import uuid
from .. import time_utility
from config.shell_config import ShellConfig

def build_entry(adapter_output):
    device = ShellConfig()

    return {
        "session_id": str(uuid.uuid4()),
        "date": now().split("T")[0],
        "time": now().split("T")[1],
        "timestamp": now(),

        "location": {
            "lat": None,
            "lon": None,
            "source": "",
            "context_location": ""
        },

        "device": {
            "device_alias": device["device_alias"],
            "device_id": device["device_id"],
            "device_battery": device.get("device_battery", ""),
            "device_thermal": device.get("device_thermal", ""),
            "device_network": device.get("device_network", ""),
            "vpn": device.get("vpn", "")
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
            "network_status": device.get("device_network", ""),
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