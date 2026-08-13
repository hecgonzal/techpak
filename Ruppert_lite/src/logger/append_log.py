# logger/append_log.py
import json
import os

def append_log(entry, path):
    """Append a JSON-serializable entry to a newline-delimited JSON file."""

    dirpath = os.path.dirname(path)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)

    try:
        text = json.dumps(entry, ensure_ascii=False)
    except (TypeError, ValueError):
        return False

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        return False

    return True
