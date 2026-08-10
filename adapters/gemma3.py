import json
import urllib.request
import time
import urllib.error

class Gemma3Adapter:
    def __init__(
        self,
        model="gemma3",
        host="http://localhost:11434" #ollama exposure port
    ):
        self.model = model
        self.host = host

    def generate(self, prompt): #response = ai.generate("hello ai")

        start_time = time.perf_counter()

        url = f"{self.host}/api/generate" #ollama generation end point

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False #False waits for prompt to finish before printing, True writes as it is generated
        }

        data = json.dumps(payload).encode("utf-8") #Converts payload to json format and then from text to bytes of data

        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json"
            },
            method="POST" #HTTP for heres some data, give me a response
        )

        try:
            with urllib.request.urlopen(request) as response:

                result = json.loads( #takes response and converts back to json
                    response.read().decode("utf-8") 
                )
        except (urllib.error.URLError, urllib.error.HTTPError) as error: #Returns error on failure

             return {
                "response": "",
                "model": self.model,
                "tokens_in": 0,
                "tokens_out": 0,
                "latency_ms": 0,
                "error": str(error),
                "raw": None
            }
        
        latency_ms = ( #Calculates latency using earlier start time
            time.perf_counter() - start_time
        ) * 1000

        return {
            "response": result.get("response", ""),
            "model": result.get(
                "model",
                self.model
            ),
            "tokens_in": result.get(
                "prompt_eval_count",
                0
            ),
            "tokens_out": result.get(
                "eval_count",
                0
            ),
            "latency_ms": round(
                latency_ms,
                2
            ),
            "error": None,
            "raw": result
        }