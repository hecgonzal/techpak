import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from . import create_msg
from Technet.services.packservice.tp_ruppertlog import _default_log


class MessageBuilderTests(unittest.TestCase):
    def test_packet_has_correlation_id_and_separate_route_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(_default_log, "path", Path(temp_dir) / "services.jsonl"):
                packet = create_msg(
                    source_device_id="device-a",
                    destination_device_id="device-b",
                    request_id="request-123",
                    netlink={"hop_count": 2, "mesh_route": ["device-x"]},
                    authorization={"audience": "tp-sysinfo"},
                    payload={"payload_type": "service.request", "content": {"field": "battery"}},
                )

        self.assertEqual(packet["msgbus"]["request_id"], "request-123")
        self.assertEqual(packet["netlink"]["hop_count"], 2)
        self.assertEqual(packet["authorization"]["audience"], "tp-sysinfo")
        self.assertEqual(packet["payload"]["payload_type"], "service.request")

    def test_request_id_is_generated_when_not_supplied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(_default_log, "path", Path(temp_dir) / "services.jsonl"):
                first = create_msg()
                second = create_msg()

        self.assertTrue(first["msgbus"]["request_id"])
        self.assertNotEqual(first["msgbus"]["request_id"], second["msgbus"]["request_id"])


if __name__ == "__main__":
    unittest.main()
