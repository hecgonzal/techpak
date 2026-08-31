"""Flexible Linux thermal sensor telemetry for tp-sysinfo."""

from pathlib import Path


THERMAL_ZONE_PATH = Path("/sys/class/thermal")
HWMON_PATH = Path("/sys/class/hwmon")


def _read(path):
	try:
		return path.read_text(encoding="ascii").strip()
	except (FileNotFoundError, OSError, UnicodeError):
		return None


def _temperature(path):
	value = _read(path)
	if value is None:
		return None
	try:
		return round(int(value) / 1000, 2)
	except ValueError:
		return None


def _thermal_zone_sensors(path):
	sensors = []
	try:
		zones = sorted(path.glob("thermal_zone*"))
	except (OSError, ValueError):
		return sensors

	for zone in zones:
		if not zone.is_dir():
			continue
		sensor_id = zone.name
		sensors.append({
			"id": sensor_id,
			"name": _read(zone / "type") or sensor_id,
			"source": "thermal_zone",
			"sensor_type": _read(zone / "type"),
			"temperature_celsius": _temperature(zone / "temp"),
		})
	return sensors


def _hwmon_sensors(path):
	sensors = []
	try:
		devices = sorted(path.glob("hwmon*"))
	except (OSError, ValueError):
		return sensors

	for device in devices:
		if not device.is_dir():
			continue
		device_name = _read(device / "name") or device.name
		for input_path in sorted(device.glob("temp*_input")):
			sensor_id = input_path.stem
			label = _read(device / sensor_id.replace("_input", "_label"))
			sensors.append({
				"id": f"{device_name}:{sensor_id}",
				"name": label or sensor_id,
				"source": "hwmon",
				"sensor_type": device_name,
				"temperature_celsius": _temperature(input_path),
			})
	return sensors


def get_thermal_info(
		thermal_zone_path=THERMAL_ZONE_PATH,
		hwmon_path=HWMON_PATH,
):
	"""Return discovered temperature sensors without applying thresholds."""
	sensors = _thermal_zone_sensors(thermal_zone_path)
	sensors.extend(_hwmon_sensors(hwmon_path))
	degradation_flags = []

	if not sensors:
		degradation_flags.append("thermal_sensors_unavailable")
	elif any(sensor["temperature_celsius"] is None for sensor in sensors):
		degradation_flags.append("thermal_reading_unavailable")

	return {
		"state": "unknown",
		"sensors": sensors,
		"headroom_celsius": None,
		"degraded": bool(degradation_flags),
		"degradation_flags": degradation_flags,
	}


if __name__ == "__main__":
	print(get_thermal_info())
