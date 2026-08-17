
import os

class PromptSchema:
    def __init__(self, path="schema/prompt_schema"):
        base = os.path.dirname(os.path.dirname(__file__))  # go up from src/ai/
        schema_path = os.path.join(base, path)

        with open(schema_path, "r", encoding="utf-8") as f:
            self.template = f.read()

    def get_template(self):
        return self.template
