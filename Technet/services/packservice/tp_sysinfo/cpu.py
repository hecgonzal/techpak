"""Lightweight Linux CPU telemetry for tp-sysinfo."""

import os


def _core_count():
	"""Return CPUs available to this process and whether a fallback was used."""
	try:
		return len(os.sched_getaffinity(0)), False
	except (AttributeError, OSError):
		count = os.cpu_count()
		return count or 1, True


def _load_average(path="/proc/loadavg"):
	"""Read Linux load averages without enumerating running processes."""
	try:
		with open(path, encoding="ascii") as loadavg_file:
			values = loadavg_file.read().split()
	except (FileNotFoundError, OSError, UnicodeError):
		return [None, None, None]

	try:
		load_average = [float(value) for value in values[:3]]
		if len(load_average) != 3:
			raise ValueError
		return load_average
	except (ValueError, TypeError):
		return [None, None, None]


def _frequency(path="/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"):
	"""Read the current CPU frequency in MHz from Linux cpufreq sysfs."""
	try:
		with open(path, encoding="ascii") as frequency_file:
			frequency_khz = int(frequency_file.read().strip())
		return round(frequency_khz / 1000, 2)
	except (FileNotFoundError, OSError, ValueError, UnicodeError):
		return None


def get_cpu_info():
	"""Return the CPU block defined by the tp-sysinfo schema.

	``load_percent`` is the one-minute Linux load average normalized by the
	CPUs available to this process. It can exceed 100 when the system is
	oversubscribed; that preserves useful saturation information.
	"""
	load_average = _load_average()
	core_count, core_count_fallback = _core_count()
	frequency_mhz = _frequency()
	degradation_flags = []

	if load_average[0] is None:
		degradation_flags.append("load_average_unavailable")
	if core_count_fallback:
		degradation_flags.append("core_count_fallback")
	if frequency_mhz is None:
		degradation_flags.append("cpu_frequency_unavailable")

	load_percent = None

	if load_average[0] is not None and core_count:
		load_percent = round(load_average[0] / core_count * 100, 2)

	return {
		"load_percent": load_percent,
		"load_average": load_average,
		"core_count": core_count,
		"frequency_mhz": frequency_mhz,
		"degraded": bool(degradation_flags),
		"degradation_flags": degradation_flags,
	}


if __name__ == "__main__":
	print(get_cpu_info())
