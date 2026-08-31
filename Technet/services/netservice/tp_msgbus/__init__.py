
"""MsgBus transport envelope builder.

Full Packet {msgbus{auth_lite{payload}}}

The msgbus layer is strictly a routing envelope. It contains only the headers
needed to deliver a packet to the correct destination:
- source and destination device identity
- priority

All other data (authorization, commands, telemetry, state) lives in nested
layers: authorization and payload.
"""


def create_msg(
	source_device_id="",
	source_device_alias="",
	destination_device_id="",
	destination_device_alias="",
	priority="normal",
	authorization=None,
	payload=None,
):
	"""Build a complete message with msgbus routing envelope.

	Args:
		source_device_id: originating device identifier
		source_device_alias: human-readable source name
		destination_device_id: target device identifier
		destination_device_alias: human-readable destination name
		priority: routing priority (normal, high, low)
		authorization: nested authorization layer (dict)
		payload: nested payload layer (dict)

	Returns:
		A complete message dict with msgbus/authorization/payload structure.
	"""
	return {
		"msgbus": {
			"source_device_id": source_device_id,
			"source_device_alias": source_device_alias,
			"destination_device_id": destination_device_id,
			"destination_device_alias": destination_device_alias,
			"priority": priority,
		},
		"authorization": authorization or {},
		"payload": payload or {},
	}


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