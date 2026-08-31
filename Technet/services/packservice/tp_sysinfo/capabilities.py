"""Device capability telemetry for tp-sysinfo.

TODO: this module is intentionally left as a stub. Capability discovery needs
more design work and engineering than the current lightweight sysinfo scope
requires, so we return an empty placeholder payload until that work is defined.
"""


def get_capabilities_info():
	"""TODO: implement real discovery of hardware and service capabilities."""
	return {
		"items": [],
		"degraded": True,
		"degradation_flags": ["capability_discovery_todo"],
	}


if __name__ == "__main__":
	print(get_capabilities_info())
