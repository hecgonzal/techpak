import json
from .logger import build_entry, append_log, load_schema
from config import ShellConfig
from system import SystemTools

class LoggingTools:
    def __init__(self):
        self.shell_config = ShellConfig()
        self.system = SystemTools()


    def append(self, entry):
        return self.append_log(entry, path=self.shell_config.log_path)

    def load_schema():
        with open("schema/schema.json") as f:
            return json.load(f)