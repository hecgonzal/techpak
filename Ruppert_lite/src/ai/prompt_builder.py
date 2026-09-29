import json
from collections.abc import Mapping

from .prompt_schema import PromptSchema


class PromptBuilder:
	"""Populate the prompt template with per-turn information."""

	def __init__(self, template=None):
		self.template = template if template is not None else PromptSchema().get_template()

	def build(self, user_message, *, config=None, commands=None, context=None):
		"""Return a complete model prompt without mutating the template."""
		if isinstance(config, Mapping):
			config_values = config
		elif config is not None and hasattr(config, "to_dict"):
			config_values = config.to_dict()
		else:
			config_values = {}

		return (
			self.template
			.replace("# CONFIG\nConfiguration values will be injected here by the PromptBuilder.",
					 f"# CONFIG\n{self._format_value(config_values, empty='No configuration provided.')}")
			.replace("# COMMANDS\nThe list of available commands will be injected here by the PromptBuilder.",
					 f"# COMMANDS\n{self._format_value(commands, empty='No commands provided.')}")
			.replace("# CONTEXT\nRecent logs, context summaries, and state snapshots will be injected here by the PromptBuilder.",
					 f"# CONTEXT\n{self._format_value(context, empty='No additional context.')}")
			.replace("# TASK\nThe specific task instruction for this interaction will be injected here.",
					 f"# TASK\nRespond to the user's request.")
			.replace("# USER\nThe raw user input will be injected here.",
					 f"# USER\n{user_message}")
		)

	@staticmethod
	def _format_value(value, *, empty):
		if value is None or value == "" or value == [] or value == {}:
			return empty
		if isinstance(value, str):
			return value
		return json.dumps(value, ensure_ascii=False, indent=2, default=str)
