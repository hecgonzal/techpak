import adapters
from adapters import Gemma3Adapter
from src.logger import append_log, load_schema, build_entry


ai = Gemma3Adapter()
prompt = ai.generate("Testing AI shell")
entry = build_entry(prompt)
append_log(entry, path="logs/test.jsonl")

