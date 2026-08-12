import adapters
import os
from adapters import Gemma3Adapter
from src.logger import append_log, load_schema, build_entry


ai = Gemma3Adapter()
prompt = ai.generate("Testing AI shell")
entry = build_entry(prompt)
success = append_log(entry, path="Ruppert_lite/logs/testlog.jsonl")
print("Entry Content:", entry)
print("Append success:", success)
print("Absolute path:", os.path.abspath("Ruppert_lite/logs/testlog.jsonl"))

