from pathlib import Path

ROOT = Path(".")

for py_file in ROOT.rglob("*.py"):
    try:
        content = py_file.read_text(encoding="utf-8")
        if "C:\\Users\\prana" in content:
            print(py_file)
    except Exception:
        pass