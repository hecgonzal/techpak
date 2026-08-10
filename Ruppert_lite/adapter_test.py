from adapters import gemma3

ai = Gemma3Adapter()
result = ai.generate("Testing AI shell")
print(result)