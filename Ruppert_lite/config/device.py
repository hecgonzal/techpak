import json

def load_device_config(path="config/device.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)