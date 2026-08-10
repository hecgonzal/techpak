import json

def load_schema():
    with open("schema/schema.json") as f:
        return json.load(f)