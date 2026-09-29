"""Techpack service status telemetry for tp-sysinfo.

TODO: this module is intentionally left as a stub. Service-status discovery
needs a larger operational model for lifecycle checks, registry lookups, and
health semantics, so we keep it explicitly deferred for now.
"""


def get_services_info():
	"""TODO: implement service-state discovery and health reporting."""
	return {
		"tp_sysinfo": "unknown",
		"tp_netlink": "unknown",
		"tp_msgbus": "unknown",
		"tp_authlite": "in_process_prototype",
		"degraded": True,
		"degradation_flags": ["service_discovery_todo", "authlite_transport_todo"],
	}


if __name__ == "__main__":
	print(get_services_info())
