"""Lightweight Linux power policy telemetry for tp-sysinfo."""

from pathlib import Path


POWER_PROFILE_PATH = Path("/sys/firmware/acpi/platform_profile")
GOVERNOR_PATH = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
BATTERY_PATH = Path("/sys/class/power_supply")


def _read(path):
	try:
		return path.read_text(encoding="ascii").strip()
	except (FileNotFoundError, OSError, UnicodeError):
		return None


def _battery_status(power_supply_path):
	try:
		for path in power_supply_path.glob("BAT*/status"):
			status = _read(path)
			if status:
				return status
	except (OSError, ValueError):
		pass
	return None


def get_power_info(
		power_profile_path=POWER_PROFILE_PATH,
		governor_path=GOVERNOR_PATH,
		battery_path=BATTERY_PATH,
):
	"""Return power mode and a conservative battery-based efficiency score."""
	degradation_flags = []
	mode = _read(power_profile_path)

	if mode is None:
		mode = _read(governor_path)
	if mode is None:
		degradation_flags.append("power_mode_unavailable")

	status = _battery_status(battery_path)
	efficiency_score = None
	if status == "Discharging":
		efficiency_score = 100
	elif status == "Charging":
		efficiency_score = 50
	elif status == "Full":
		efficiency_score = 100
	else:
		degradation_flags.append("power_efficiency_unavailable")

	return {
		"mode": mode,
		"efficiency_score": efficiency_score,
		"degraded": bool(degradation_flags),
		"degradation_flags": degradation_flags,
	}


if __name__ == "__main__":
	print(get_power_info())
