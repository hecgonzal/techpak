"""Lightweight Linux storage telemetry for tp-sysinfo."""

import os


def get_storage_info(mount_point="/"):
	"""Return storage usage for one mount without scanning filesystems."""
	try:
		stats = os.statvfs(mount_point)
		block_size = stats.f_frsize or stats.f_bsize
		total_bytes = stats.f_blocks * block_size
		available_bytes = stats.f_bavail * block_size
		used_bytes = max(total_bytes - available_bytes, 0)
		used_percent = round(used_bytes / total_bytes * 100, 2) if total_bytes else None
	except (AttributeError, OSError, ValueError):
		return [{
			"mount": mount_point,
			"used_percent": None,
			"used_bytes": None,
			"available_bytes": None,
			"total_bytes": None,
			"degraded": True,
			"degradation_flags": ["storage_unavailable"],
		}]

	return [{
		"mount": mount_point,
		"used_percent": used_percent,
		"used_bytes": used_bytes,
		"available_bytes": available_bytes,
		"total_bytes": total_bytes,
		"degraded": False,
		"degradation_flags": [],
	}]


if __name__ == "__main__":
	print(get_storage_info())
