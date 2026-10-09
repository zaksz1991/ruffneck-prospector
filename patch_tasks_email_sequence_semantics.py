from pathlib import Path
import ast

path = Path(r".\backend\app\tasks.py")
source = path.read_text(encoding="utf-8")

old = '''            if (
                meta.get(
                    "email_valid"
                )
                is False
                or meta.get(
                    "email_status"
                )
                in (
                    "invalid_syntax",
                    "disposable",
                    "no_mx",
                    "undeliverable",
                )
            ):
'''

new = '''            if meta.get(
                "email_status"
            ) in (
                "invalid_syntax",
                "disposable",
                "no_mx",
                "undeliverable",
                "risky",
            ):
'''

count = source.count(old)

if count != 1:
    raise RuntimeError(
        f"Expected exactly 1 sequence email-validation block, found {count}."
    )

patched = source.replace(old, new, 1)

ast.parse(patched.lstrip("\ufeff"))

backup = Path(r".\backend\app\tasks.py.bak-email-sequence-semantics-v1")

if not backup.exists():
    backup.write_text(source, encoding="utf-8")

path.write_text(patched, encoding="utf-8")

print("tasks.py sequence email-validation semantics patched successfully.")
