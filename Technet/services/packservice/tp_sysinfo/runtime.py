"""Lightweight Linux runtime telemetry for tp-sysinfo."""

from pathlib import Path


UPTIME_PATH = Path("/proc/uptime")
BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")


def _read(path):
	try:
		return path.read_text(encoding="ascii").strip()
	except (FileNotFoundError, OSError, UnicodeError):
		return None


def _uptime_seconds(path):
	value = _read(path)
	if value is None:
		return None
	try:
		return round(float(value.split()[0]), 2)
	except (IndexError, ValueError):
		return None


def get_runtime_info(
		uptime_path=UPTIME_PATH,
		boot_id_path=BOOT_ID_PATH,
):
	"""Return uptime, boot identity, and the local runtime state."""
	uptime_seconds = _uptime_seconds(uptime_path)
	boot_id = _read(boot_id_path)
	degradation_flags = []

	if uptime_seconds is None:
		degradation_flags.append("uptime_unavailable")
	if not boot_id:
		boot_id = None
		degradation_flags.append("boot_id_unavailable")

	return {
		"uptime_seconds": uptime_seconds,
		"boot_id": boot_id,
		"device_state": "running" if not degradation_flags else "unknown",
		"degraded": bool(degradation_flags),
		"degradation_flags": degradation_flags,
	}


if __name__ == "__main__":
	print(get_runtime_info())
