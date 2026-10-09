from pathlib import Path
import ast

path = Path(r".\backend\app\enrichment.py")
source = path.read_text(encoding="utf-8")

old = '''            if not v.get("valid"):
                result["email_confidence"] = min(
                    result.get(
                        "email_confidence"
                    )
                    or 0,
                    20,
                )

            elif v.get("status") == "risky":
                result["email_confidence"] = min(
                    result.get(
                        "email_confidence"
                    )
                    or 50,
                    55,
                )
'''

new = '''            status = v.get("status")

            if status == "risky":
                # Risky is not verified, but the address may still
                # be plausible. Keep a moderate confidence ceiling.
                result["email_confidence"] = min(
                    result.get(
                        "email_confidence"
                    )
                    or 50,
                    55,
                )

            elif status == "unknown":
                # Syntax + MX confirms only the domain, not the
                # specific mailbox. Preserve source confidence.
                pass

            elif not v.get("valid"):
                # Definitive negative verification results should
                # strongly reduce the email confidence.
                result["email_confidence"] = min(
                    result.get(
                        "email_confidence"
                    )
                    or 0,
                    20,
                )
'''

count = source.count(old)

if count != 1:
    raise RuntimeError(
        f"Expected exactly 1 email verification confidence block, found {count}."
    )

patched = source.replace(old, new, 1)

ast.parse(patched.lstrip("\ufeff"))

backup = Path(r".\backend\app\enrichment.py.bak-email-verification-semantics-v1")

if not backup.exists():
    backup.write_text(source, encoding="utf-8")

path.write_text(patched, encoding="utf-8")

print("enrichment.py email verification confidence semantics patched successfully.")
