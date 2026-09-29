
from pathlib import Path

class PromptSchema:
    def __init__(self, path=None):
        project_root = Path(__file__).resolve().parents[2]
        schema_path = (
            Path(path)
            if path is not None and Path(path).is_absolute()
            else project_root / path
            if path is not None
            else project_root / "ruppert_schema" / "prompt_schema.txt"
        )
        self.template = schema_path.read_text(encoding="utf-8")

    def get_template(self):
        return self.template
