from uuid import uuid4

from adapters import load_adapter
from config import ShellConfig
from src.logger import LoggingTools

from .prompt_builder import PromptBuilder


class ConversationService:
	"""Coordinate prompt construction, model calls, and per-turn logging."""

	def __init__(
		self,
		adapter=None,
		logging_tools=None,
		prompt_builder=None,
		shell_config=None,
		commands=None,
		session_id=None,
	):
		self.shell_config = shell_config or ShellConfig()
		self.adapter = adapter or load_adapter(self.shell_config.ai_model)
		self.logging_tools = logging_tools or LoggingTools()
		self.prompt_builder = prompt_builder or PromptBuilder()
		self.commands = commands
		self.session_id = session_id or str(uuid4())

	def start_new_session(self):
		"""Start a fresh log session and return its ID."""
		self.session_id = str(uuid4())
		return self.session_id

	def handle_message(self, user_message, *, context=None):
		"""Send one user turn to the model, log it, and return its result."""
		if context is None and hasattr(self.logging_tools, "load_context"):
			context = self.logging_tools.load_context(user_message)

		prompt = self.prompt_builder.build(
			user_message,
			config=self.shell_config,
			commands=self.commands,
			context=context,
		)
		adapter_output = self.adapter.generate(prompt)

		# Keep the original user message distinct from the composed system prompt.
		raw = dict(adapter_output.get("raw") or {})
		raw.setdefault("prompt", prompt)
		raw["user_message"] = user_message
		adapter_output["raw"] = raw

		entry = self.logging_tools.build_entry(
			adapter_output,
			session_id=self.session_id,
			user_message=user_message,
		)
		adapter_output["log_saved"] = self.logging_tools.append(entry)
		return adapter_output
