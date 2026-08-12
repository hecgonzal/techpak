import json
import os
from .. import time_utility
from config.shell_config import ShellConfig

def append_log(entry, path="Ruppert_lite/logs/testlog.jsonl"):
    """Append a JSON-serializable entry to a newline-delimited JSON file.

    Ensures the target directory exists. Returns True on success, False on failure.
    """
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