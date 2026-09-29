from config import ShellConfig
from src.logger import LoggingTools
from src.ai.conversation_service import ConversationService
from adapters import load_adapter

from .commands import RuppertCommands


class RuppertShell:
    def __init__(self):
        self.shell_config = ShellConfig()
        self.logging_tools = LoggingTools()
        self.adapter = load_adapter(self.shell_config.ai_model)
        self.command_handler = RuppertCommands(
            self.shell_config,
            self.adapter,
            self.logging_tools,
        )
        self.conversation_service = ConversationService(
            adapter=self.adapter,
            logging_tools=self.logging_tools,
            shell_config=self.shell_config,
            commands={
                name: metadata["description"]
                for name, metadata in self.command_handler.commands.items()
            },
        )

    def chat(self):
        print(f"Ruppert-lite v {self.shell_config.rupert_shell_version} - {self.shell_config.ai_model}\n")

#Command loop
        while True:
            call = input("You: ")
            if call.startswith("/"):
                self.command_handler.handle_command(call)
                continue

            response_block = self.conversation_service.handle_message(call)
            if response_block.get("error"):
                print(f"Ruppert error: {response_block['error']}\n")
            else:
                print(f"Ruppert: {response_block['response']}\n")