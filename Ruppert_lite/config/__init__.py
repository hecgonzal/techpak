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
        self.log_path = data.get("log_path", "Ruppert_lite/logs/testlog.jsonl")
        self.master_log_path = data.get("master_log_path", self.log_path)
        self.working_log_path = data.get("working_log_path", "Ruppert_lite/logs/workinglog.jsonl")
        self.tech_services_log_path = data.get(
            "tech_services_log_path",
            "Ruppert_lite/logs/TechServicesLog.jsonl",
        )
        self.ai_model = data["ai_model"]
        self.working_log_adapter = data.get("working_log_adapter", self.ai_model)

        self.rupert_shell_version = data["rupert_shell_version"]

    def to_dict(self):
        """Return config as a dictionary just in case."""
        return {
            "device_alias": self.device_alias,
            "device_id": self.device_id,
            "device_network": self.device_network,
            "vpn": self.vpn,
            "device_battery": self.device_battery,
            "device_thermal": self.device_thermal,
            "ai_model": self.ai_model,
            "working_log_adapter": self.working_log_adapter,
        }