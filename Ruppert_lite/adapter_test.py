import adapters
import os
from adapters import Gemma3Adapter
from src.logger import LoggingTools, logger
from config import ShellConfig
from adapters import load_adapter

logging_tools = LoggingTools()
ai = Gemma3Adapter()

config = ShellConfig()
ai = load_adapter(config.ai_model)
adapter_output = ai.generate("Testing AI shell")
entry = logger.build_entry(adapter_output)
success = logger.append_log(entry, path=config.log_path)
print("Entry Content:", entry)
print("Append success:", success)
print("Absolute path:", os.path.abspath(config.log_path))

