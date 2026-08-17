import json
import urllib.request
import time
import urllib.error

class Gemma3Adapter:
    def __init__(
        self,
        model="gemma3",
        host="http://localhost:11434"
    ):
        self.model = model
        self.host = host

    def generate(self, prompt):
        start_time = time.perf_counter()
        url = f"{self.host}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))

        except (urllib.error.URLError, urllib.error.HTTPError) as error:
            latency_ms = (time.perf_counter() - start_time) * 1000

            return {
                "raw": {"prompt": prompt},
                "response": "",
                "model": self.model,
                "tokens_in": 0,
                "tokens_out": 0,
                "latency_ms": round(latency_ms, 2),
                "error": str(error)
            }

        latency_ms = (time.perf_counter() - start_time) * 1000

        return {
            "raw": {"prompt": prompt},
            "response": result.get("response", ""),
            "model": result.get("model", self.model),
            "tokens_in": result.get("prompt_eval_count", 0),
            "tokens_out": result.get("eval_count", 0),
            "latency_ms": round(latency_ms, 2),
            "error": None
        }
