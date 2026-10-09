from pathlib import Path
import ast

path = Path(r".\backend\app\enrichment.py")
source = path.read_text(encoding="utf-8")

old = '''    if result.get("email_candidates"):
        result.update(
            {
                "email": result["email_candidates"][0],
                "email_confidence": 35,
                "email_source": "pattern_guess",
                "enrichment_status": "email_guessed",
            }
        )
'''

new = '''    if result.get("email_candidates"):
        result.update(
            {
                "email": None,
                "email_confidence": 0,
                "email_source": "pattern_guess",
                "enrichment_status": "email_guessed",
            }
        )
'''

count = source.count(old)

if count != 1:
    raise RuntimeError(
        f"Expected exactly 1 pattern fallback block, found {count}."
    )

patched = source.replace(old, new, 1)

ast.parse(patched.lstrip("\ufeff"))

backup = Path(r".\backend\app\enrichment.py.bak-email-v1")

if not backup.exists():
    backup.write_text(source, encoding="utf-8")

path.write_text(patched, encoding="utf-8")

print("enrichment.py email pattern fallback patched successfully.")
