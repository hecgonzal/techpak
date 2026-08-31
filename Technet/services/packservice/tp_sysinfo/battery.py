"""Lightweight Linux battery telemetry for tp-sysinfo."""

from pathlib import Path


POWER_SUPPLY_PATH = Path("/sys/class/power_supply")


def _read(path):
	try:
		return path.read_text(encoding="ascii").strip()
	except (FileNotFoundError, OSError, UnicodeError):
		return None


def _battery_path(power_supply_path):
	try:
		for path in power_supply_path.iterdir():
			if path.name.startswith("BAT") and path.is_dir():
				return path
	except (FileNotFoundError, OSError):
		return None
	return None


def _online(power_supply_path):
	"""Return whether an external power supply reports online."""
	try:
		for path in power_supply_path.iterdir():
			if path.name.startswith("BAT"):
				continue
			if _read(path / "online") == "1":
				return True
	except (FileNotFoundError, OSError):
		pass
	return False


def get_battery_info(power_supply_path=POWER_SUPPLY_PATH):
	"""Return battery percentage, power state, and remaining time."""
	battery_path = _battery_path(power_supply_path)
	degradation_flags = []

	if battery_path is None:
		return {
			"percent": None,
			"plugged": _online(power_supply_path),
			"charging": None,
			"seconds_remaining": None,
			"degraded": True,
			"degradation_flags": ["battery_unavailable"],
		}

	percent_text = _read(battery_path / "capacity")
	status = _read(battery_path / "status")
	percent = None
	if percent_text is not None:
		try:
			percent = float(percent_text)
		except ValueError:
			degradation_flags.append("battery_percent_unavailable")
	else:
		degradation_flags.append("battery_percent_unavailable")

	charging = None
	if status in ("Charging", "Discharging", "Full", "Not charging"):
		charging = status == "Charging"
	else:
		degradation_flags.append("battery_status_unavailable")

	seconds_remaining = None
	if status == "Charging":
		time_path = battery_path / "time_to_full_now"
	elif status == "Discharging":
		time_path = battery_path / "time_to_empty_now"
	else:
		time_path = None

	if time_path is not None:
		time_text = _read(time_path)
		if time_text is None:
			degradation_flags.append("battery_time_unavailable")
		else:
			try:
				seconds_remaining = int(time_text)
			except ValueError:
				degradation_flags.append("battery_time_unavailable")

	return {
		"percent": percent,
		"plugged": _online(power_supply_path),
		"charging": charging,
		"seconds_remaining": seconds_remaining,
		"degraded": bool(degradation_flags),
		"degradation_flags": degradation_flags,
	}


if __name__ == "__main__":
	print(get_battery_info())
