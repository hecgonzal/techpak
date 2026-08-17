from ..config import ShellConfig
from src.logger import LoggingTools, logger
from adapters import load_adapter


class RuppertShell:
    def __init__(self):
        self.shell_config = ShellConfig()
        self.logging_tools = LoggingTools()
        self.adapter = load_adapter(self.shell_config.ai_model)

    def chat(self):
        print(f"Ruppert-lite v {self.shell_config.rupert_shell_version} - {self.shell_config.ai_model}\n")

#Command loop
        while True:
            call = input("You: ")
            if call.startswith("/"):
                self.commands(call)
                continue

#AI response, not very human readable
            response_block = self.adapter_response(call)

#Logging
            entry = self.logging_tools.build_entry(response_block)
            self.logging_tools.append(entry)

            print(f"Ruppert: {response_block['response']}\n")