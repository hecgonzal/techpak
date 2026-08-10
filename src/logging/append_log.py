import json

def append_entry(entry, path="logs/test.jsonl"):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")