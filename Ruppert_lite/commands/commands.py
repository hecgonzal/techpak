from src.logger import LoggingTools
from config import ShellConfig
import json


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
            "condense": {
                "handler": self.cmd_condense,
                "description": "Manually use the configured maintenance model to index master-log records into the working log; run during idle time.",
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

    def cmd_config(self, args):
        if args:
            print("Usage: /config")
            return
        print(json.dumps(self.shell_config.to_dict(), ensure_ascii=False, indent=2))

    def cmd_set(self, args):
        if len(args) < 2:
            print("Usage: /set <key> <value>")
            return
        key, value = args[0], " ".join(args[1:])
        allowed = self.shell_config.to_dict()
        if key not in allowed:
            print(f"Unknown or protected configuration key: {key}")
            return
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value
        setattr(self.shell_config, key, parsed_value)
        print(f"Updated {key} for this shell session only.")

    def cmd_condense(self, args):
        if len(args) > 1:
            print("Usage: /condense [maximum records]")
            return
        try:
            limit = int(args[0]) if args else 100
            report = self.logging_tools.condense_master_log(max_records=limit)
        except (OSError, TypeError, ValueError) as error:
            print(f"Condensation could not start: {error}")
            return
        print(
            "Working-log condensation complete: "
            f"processed={report['processed']}, skipped={report['skipped']}, "
            f"failed={report['failed']}, adapter={report['model']}"
        )
        for failure in report["failures"][:5]:
            print(f"- {failure['source_record_id']}: {failure['error']}")

    def cmd_help(self, args):
        if args:
            print("Usage: /help")
            return
        for name, metadata in self.commands.items():
            print(f"/{name}: {metadata['description']}")