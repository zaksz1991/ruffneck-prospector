from pathlib import Path

path = Path(r".\backend\app\scrapers\google_search.py")
text = path.read_text(encoding="utf-8")

old = '''                1
                if self._is_homepage_url(
                    item.get("href", "")
                )
                else 0,
'''

new = '''                self._page_priority(
                    item.get("href", "")
                ),
'''

if old not in text:
    raise RuntimeError(
        "Could not locate the nonexistent _is_homepage_url() sort block."
    )

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")

print("HOMEPAGE SORT FIX APPLIED")
