from pathlib import Path
import ast

path = Path(r".\backend\app\email_verify.py")
source = path.read_text(encoding="utf-8")

old = '''        if res == "risky":
            result.update({"valid": True, "status": "risky", "confidence": 50})
            return result
'''

new = '''        if res == "risky":
            # Risky means the mailbox is not sufficiently verified.
            result.update({"valid": False, "status": "risky", "confidence": 50})
            return result
'''

count = source.count(old)

if count != 1:
    raise RuntimeError(
        f"Expected exactly 1 Hunter risky block, found {count}."
    )

patched = source.replace(old, new, 1)

ast.parse(patched.lstrip("\ufeff"))

backup = Path(r".\backend\app\email_verify.py.bak-risky-v1")

if not backup.exists():
    backup.write_text(source, encoding="utf-8")

path.write_text(patched, encoding="utf-8")

print("email_verify.py Hunter risky semantics patched successfully.")
