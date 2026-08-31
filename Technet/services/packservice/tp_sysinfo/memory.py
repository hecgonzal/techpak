"""Lightweight Linux memory telemetry for tp-sysinfo."""


def _memory_values(path="/proc/meminfo"):
	"""Read only the memory values needed by the sysinfo packet."""
	values = {}

	try:
		with open(path, encoding="ascii") as meminfo_file:
			for line in meminfo_file:
				key, separator, value = line.partition(":")
				if separator and key in ("MemTotal", "MemAvailable"):
					parts = value.split()
					if parts and parts[0].isdigit():
						values[key] = int(parts[0]) * 1024
	except (FileNotFoundError, OSError, UnicodeError):
		return {}

	return values


def get_memory_info():
	"""Return memory totals in bytes and the used percentage."""
	values = _memory_values()
	total_bytes = values.get("MemTotal")
	available_bytes = values.get("MemAvailable")
	degradation_flags = []

	if total_bytes is None:
		degradation_flags.append("memory_total_unavailable")
	if available_bytes is None:
		degradation_flags.append("memory_available_unavailable")

	used_bytes = None
	used_percent = None
	if total_bytes is not None and available_bytes is not None:
		used_bytes = max(total_bytes - available_bytes, 0)
		if total_bytes:
			used_percent = round(used_bytes / total_bytes * 100, 2)

	return {
		"used_percent": used_percent,
		"used_bytes": used_bytes,
		"available_bytes": available_bytes,
		"total_bytes": total_bytes,
		"degraded": bool(degradation_flags),
		"degradation_flags": degradation_flags,
	}


if __name__ == "__main__":
	print(get_memory_info())
