from .gemma3 import Gemma3Adapter

ADAPTERS = {
    "Gemma3Adapter": Gemma3Adapter
}

def load_adapter(model_name):
    adapter_cls = ADAPTERS.get(model_name)
    if not adapter_cls:
        raise ValueError(f"Unknown model: {model_name}")
    return adapter_cls()