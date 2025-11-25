import deepgram
import pkgutil

print("Deepgram version:", getattr(deepgram, "__version__", "Unknown"))
print("\nTop level attributes:")
print(dir(deepgram))

print("\nSubmodules:")
if hasattr(deepgram, "__path__"):
    for importer, modname, ispkg in pkgutil.iter_modules(deepgram.__path__):
        print(f"Found submodule: {modname}")
        try:
            module = __import__(f"deepgram.{modname}", fromlist=["*"])
            print(f"  Attributes in {modname}: {dir(module)}")
        except Exception as e:
            print(f"  Could not import {modname}: {e}")
