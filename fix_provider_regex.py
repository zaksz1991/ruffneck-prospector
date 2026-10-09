from pathlib import Path

path = Path(r".\backend\app\scrapers\google_search.py")
text = path.read_text(encoding="utf-8")

old = r'''rf"\\b{re.escape(role)}\\b"'''
new = r'''rf"\b{re.escape(role)}\b"'''

if old not in text:
    raise SystemExit("TARGET REGEX NOT FOUND")

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("REGEX FIXED")
