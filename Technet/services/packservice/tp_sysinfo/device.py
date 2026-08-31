"""Device identity telemetry loaded from the local device configuration."""

import json
from pathlib import Path


DEFAULT_CONFIG_PATH = (
	Path(__file__).resolve().parents[3] / "Ruppert_lite" / "config" / "device.json"
)


def get_device_info(config_path=None):
	"""Return the configured device alias and type for the sysinfo packet."""
	path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

	try:
		with path.open(encoding="utf-8") as config_file:
			config = json.load(config_file)
	except (FileNotFoundError, OSError, json.JSONDecodeError):
		return {
			"alias": None,
			"type": None,
			"degraded": True,
			"degradation_flags": ["device_config_unavailable"],
		}

	alias = config.get("device_alias")
	device_type = config.get("device_type")
	degradation_flags = []
	device_architecture = config.get("device_architecture")
	device_id = config.get("device_id")

	if not isinstance(alias, str) or not alias.strip():
		alias = None
		degradation_flags.append("device_alias_unavailable")

	if not isinstance(device_type, str) or not device_type.strip():
		device_type = None
		degradation_flags.append("device_type_unavailable")

	return {
		"id": device_id,
		"alias": alias,
		"type": device_type,
		"degraded": bool(degradation_flags),
		"degradation_flags": degradation_flags,
		"architecture": device_architecture
	}


if __name__ == "__main__":
	print(get_device_info())
