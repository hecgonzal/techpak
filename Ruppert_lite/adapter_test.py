import adapters
import os
from adapters import Gemma3Adapter
from src.logger import LoggingTools
from config.shell_config import ShellConfig

logging_tools = LoggingTools()
ai = Gemma3Adapter()

prompt = ai.generate("Testing AI shell")

entry = LoggingTools().build_entry(prompt)
success = LoggingTools().append(entry)
print("Entry Content:", entry)
print("Append success:", success)
print("Absolute path:", os.path.abspath(logging_tools.shell_config.log_path))

