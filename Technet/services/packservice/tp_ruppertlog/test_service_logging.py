import json
import tempfile
import unittest
from pathlib import Path

from . import TechServicesLog, service_logged
from Technet.services.netservice.tp_netlink import get_netlink_packet
from Technet.services.packservice.tp_ruppertlog import _default_log


class TechServicesLogTests(unittest.TestCase):
    def test_decorator_records_start_and_completion_with_correlation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = TechServicesLog(Path(temp_dir) / "services.jsonl")

            @service_logged("example-service", tech_services_log=logger)
            def get_data(request_id=None):
                return {"value": 7, "request_id": request_id}

            self.assertEqual(
                get_data(request_id="request-42"),
                {"value": 7, "request_id": "request-42"},
            )
            events = [
                json.loads(line)
                for line in logger.path.read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual([event["status"] for event in events], ["started", "success"])
            self.assertEqual(events[0]["call_id"], events[1]["call_id"])
            self.assertEqual(events[1]["request_id"], "request-42")
            self.assertNotIn("value", events[1])

    def test_decorator_records_failure_and_reraises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = TechServicesLog(Path(temp_dir) / "services.jsonl")

            @service_logged("example-service", tech_services_log=logger)
            def failing_service():
                raise ValueError("bad request")

            with self.assertRaisesRegex(ValueError, "bad request"):
                failing_service()

            events = [
                json.loads(line)
                for line in logger.path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual([event["status"] for event in events], ["started", "error"])
            self.assertEqual(events[1]["error"], "bad request")

    def test_netlink_public_entry_point_is_instrumented(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = _default_log.path
            _default_log.path = Path(temp_dir) / "services.jsonl"
            try:
                packet = get_netlink_packet()
            finally:
                _default_log.path = original_path

            events = [
                json.loads(line)
                for line in (Path(temp_dir) / "services.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("hop_count", packet)
            self.assertEqual([event["status"] for event in events], ["started", "success"])
            self.assertEqual(events[0]["service"], "tp-netlink")


if __name__ == "__main__":
    unittest.main()
