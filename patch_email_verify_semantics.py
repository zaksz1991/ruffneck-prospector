from pathlib import Path
import ast

path = Path(r".\backend\app\email_verify.py")
source = path.read_text(encoding="utf-8")

old = '''    # Local pass: syntax + MX
    result.update({
        "valid": True,
        "status": "ok",
        "confidence": 65,  # moderate without external verifier
    })
    return result
'''

new = '''    # Local pass: syntax + MX confirms only that the domain
    # can receive mail. It does NOT confirm that this
    # specific mailbox exists.
    result.update({
        "valid": False,
        "status": "unknown",
        "confidence": 40,
        "details": {
            **result.get("details", {}),
            "verification_scope": "domain_only",
        },
    })
    return result
'''

count = source.count(old)

if count != 1:
    raise RuntimeError(
        f"Expected exactly 1 local verification block, found {count}."
    )

patched = source.replace(old, new, 1)

ast.parse(patched.lstrip("\ufeff"))

backup = Path(r".\backend\app\email_verify.py.bak-semantics-v1")

if not backup.exists():
    backup.write_text(source, encoding="utf-8")

path.write_text(patched, encoding="utf-8")

print("email_verify.py verification semantics patched successfully.")
