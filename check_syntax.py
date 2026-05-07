import ast, sys

files = ["dataprove.py", "socialprove.py", "codeprove.py", "newsprove.py", "provart.py"]
ok = True
for f in files:
    try:
        ast.parse(open(f).read())
        print(f"{f}: OK")
    except SyntaxError as e:
        print(f"{f}: SYNTAX ERROR — {e}")
        ok = False
sys.exit(0 if ok else 1)
