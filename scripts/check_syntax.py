import ast
import sys

files = ["common.py", "proofsnap_capture.py", "newsprove.py", "socialprove.py", "monitor.py", "status.py"]
ok = True
for f in files:
    try:
        with open(f, encoding="utf-8") as source:
            ast.parse(source.read())
        print(f"{f}: OK")
    except SyntaxError as e:
        print(f"{f}: SYNTAX ERROR - {e}")
        ok = False
sys.exit(0 if ok else 1)
