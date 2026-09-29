
"""MsgBus transport envelope builder.

Packet layers: msgbus routing headers, netlink route metadata,
authorization material, and service payload.

The msgbus layer is strictly a routing envelope. It contains only the headers
needed to deliver a packet to the correct destination:
- source and destination device identity
- priority

All other data (authorization, commands, telemetry, state) lives in nested
layers: authorization and payload.
"""

import uuid
from ...packservice.tp_ruppertlog import service_logged
from ..tp_authlite.canonical import validate_packet_shape, validate_json_value


@service_logged("tp-msgbus")
def create_msg(
	source_device_id="",
	source_device_alias="",
	destination_device_id="",
	destination_device_alias="",
	priority="normal",
	request_id=None,
	netlink=None,
	authorization=None,
	payload=None,
):
	"""Build a legacy unsigned transport-envelope dictionary.

	This compatibility helper does not create a packet-version-1 Authlite packet
	and must not be used as an authenticated request. Build requests with
	`tp_authlite.build_request_packet()` and pass them through
	`attach_route_metadata()` instead.

	Args:
		source_device_id: originating device identifier
		source_device_alias: human-readable source name
		destination_device_id: target device identifier
		destination_device_alias: human-readable destination name
		priority: routing priority (normal, high, low)
		request_id: correlation ID shared by request and response
		netlink: mutable hop/route metadata, separate from authorization
		authorization: nested authorization layer (dict)
		payload: nested payload layer (dict)

	Returns:
		A complete message dict with msgbus/authorization/payload structure.
	"""
	return {
		"msgbus": {
			"request_id": request_id or str(uuid.uuid4()),
			"source_device_id": source_device_id,
			"source_device_alias": source_device_alias,
			"destination_device_id": destination_device_id,
			"destination_device_alias": destination_device_alias,
			"priority": priority,
		},
		"netlink": netlink or {},
		"authorization": authorization or {},
		"payload": payload or {},
	}


def attach_route_metadata(packet, route_metadata):
	"""Return a routed packet copy without changing Authlite-protected fields."""
	validated = validate_packet_shape(packet)
	if not isinstance(route_metadata, dict):
		raise ValueError("route_metadata must be a JSON object")
	validate_json_value(route_metadata)
	if len(route_metadata) > 32:
		raise ValueError("route_metadata has too many fields")
	routed_packet = dict(validated)
	routed_packet["netlink"] = dict(route_metadata)
	validate_packet_shape(routed_packet)
	return routed_packet


if __name__ == "__main__":
	msg = create_msg(
		source_device_id="device-001",
		source_device_alias="test-device",
		destination_device_id="device-002",
		destination_device_alias="target-device",
		priority="normal",
	)
	import json
	print(json.dumps(msg, indent=2))