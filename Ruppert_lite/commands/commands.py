from src.logger import LoggingTools
from config import ShellConfig
from adapters import load_adapter


class RuppertCommands:
    def __init__(self, shell_config: ShellConfig, adapter, logging_tools: LoggingTools):
        # Use the objects passed in, don’t recreate them
        self.shell_config = shell_config
        self.adapter = adapter
        self.logging_tools = logging_tools

        self.commands = {
            "exit": {
                "handler": self.cmd_exit,
                "description": "Exit the Rupert shell.",
            },
            "config": {
                "handler": self.cmd_config,
                "description": "Show current configuration values.",
            },
            "set": {
                "handler": self.cmd_set,
                "description": "Set a configuration key to a new value.",
            },
            "help": {
                "handler": self.cmd_help,
                "description": "Show AI-generated help for all commands.",
            },
        }

    def handle_command(self, input_command: str):
        command = input_command[1:]  # Remove leading '/'
        parts = command.split()
        if not parts:
            return

        name = parts[0]
        args = parts[1:]

        if name in self.commands:
            return self.commands[name]["handler"](args)
        else:
            print(f"Unknown command: /{name}")

    def cmd_exit(self, args):
        print("Goodbye!")
        raise SystemExit

    def cmd_help(self, args):
        mode = args[0] if args else "short and simple"

        command_list = "\n".join(
            f"- /{name}: {meta['description']}"
            for name, meta in self.commands.items()
        )

        # TODO: pull recent context from logs
        context = ""

        call = self.build_help_prompt(command_list, context, mode)

        adapter_output = self.adapter.generate(call)
        entry = self.logging_tools.build_entry(adapter_output)
        self.logging_tools.append(entry)

        print(adapter_output["response"])