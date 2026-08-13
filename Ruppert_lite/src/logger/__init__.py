from .append_log import append_log
from .load_schema import load_schema
from .build_entry import build_entry
from config.shell_config import ShellConfig
from system import SystemTools

class LoggingTools:
    def __init__(self):
        self.shell_config = ShellConfig()
        self.system = SystemTools()
        self.append_log = append_log()
        self.load_schema = load_schema()
        self.build_entry = build_entry()

    def append(self, entry):
        return self.append_log(entry, path=self.shell_config.log_path)