import os
import json

class ShellConfig:
    def __init__(self, path="config/device.json"):
        base = os.path.dirname(__file__)
        device_path =os.path.join(base, "device.json")
        with open(device_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.device_alias = data["device_alias"]
        self.device_id = data["device_id"]
        self.device_network = data["device_network"]
        self.vpn = data["vpn"]
        self.device_battery = data["device_battery"]
        self.device_thermal = data["device_thermal"]

    def to_dict(self):
        """Return config as a dictionary for embedding in logs."""
        return {
            "device_alias": self.device_alias,
            "device_id": self.device_id,
            "device_network": self.device_network,
            "vpn": self.vpn,
            "device_battery": self.device_battery,
            "device_thermal": self.device_thermal,
        }