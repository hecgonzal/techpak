import json
import unittest
import urllib.error
from unittest.mock import patch

from adapters import Gemma3Adapter


class Gemma3AdapterTests(unittest.TestCase):
	@patch("adapters.gemma3.urllib.request.urlopen")
	def test_generate_posts_prompt_and_normalizes_response(self, mock_urlopen):
		response = mock_urlopen.return_value.__enter__.return_value
		response.read.return_value = json.dumps(
			{
				"response": "Hello from the fake model",
				"model": "gemma3:latest",
				"prompt_eval_count": 4,
				"eval_count": 6,
			}
		).encode("utf-8")
		adapter = Gemma3Adapter(model="gemma3:latest", host="http://ollama.test:11434")

		result = adapter.generate("Say hello")

		request = mock_urlopen.call_args.args[0]
		self.assertEqual(request.full_url, "http://ollama.test:11434/api/generate")
		self.assertEqual(request.method, "POST")
		self.assertEqual(request.get_header("Content-type"), "application/json")
		self.assertEqual(
			json.loads(request.data.decode("utf-8")),
			{"model": "gemma3:latest", "prompt": "Say hello", "stream": False},
		)
		self.assertEqual(result["raw"], {"prompt": "Say hello"})
		self.assertEqual(result["response"], "Hello from the fake model")
		self.assertEqual(result["model"], "gemma3:latest")
		self.assertEqual(result["tokens_in"], 4)
		self.assertEqual(result["tokens_out"], 6)
		self.assertIsNone(result["error"])
		self.assertGreaterEqual(result["latency_ms"], 0)

	@patch("adapters.gemma3.urllib.request.urlopen")
	def test_generate_uses_defaults_for_optional_response_fields(self, mock_urlopen):
		response = mock_urlopen.return_value.__enter__.return_value
		response.read.return_value = b'{"response": "Ready"}'
		adapter = Gemma3Adapter()

		result = adapter.generate("Check status")

		request = mock_urlopen.call_args.args[0]
		self.assertEqual(request.full_url, "http://localhost:11434/api/generate")
		self.assertEqual(result["response"], "Ready")
		self.assertEqual(result["model"], "gemma3")
		self.assertEqual(result["tokens_in"], 0)
		self.assertEqual(result["tokens_out"], 0)
		self.assertIsNone(result["error"])

	@patch("adapters.gemma3.urllib.request.urlopen")
	def test_generate_returns_connection_error_without_raising(self, mock_urlopen):
		mock_urlopen.side_effect = urllib.error.URLError("Ollama is unavailable")
		adapter = Gemma3Adapter()

		result = adapter.generate("This should not need Ollama")

		self.assertEqual(result["response"], "")
		self.assertEqual(result["model"], "gemma3")
		self.assertEqual(result["tokens_in"], 0)
		self.assertEqual(result["tokens_out"], 0)
		self.assertIn("Ollama is unavailable", result["error"])
		self.assertGreaterEqual(result["latency_ms"], 0)


if __name__ == "__main__":
	unittest.main()

