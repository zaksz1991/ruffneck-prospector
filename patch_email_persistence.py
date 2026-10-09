from pathlib import Path
import ast

path = Path(r".\backend\app\tasks.py")
source = path.read_text(encoding="utf-8")

old = '''            if (
                email
                and not _is_fake_linkedin_email(
                    email
                )
            ):

                update[
                    "email"
                ] = email

                update[
                    "email_confidence"
                ] = data.get(
                    "email_confidence",
                    0,
                )
'''

new = '''            if data.get(
                "email_source"
            ) == "pattern_guess":

                update[
                    "email"
                ] = None

                update[
                    "email_confidence"
                ] = 0

            elif (
                email
                and not _is_fake_linkedin_email(
                    email
                )
            ):

                update[
                    "email"
                ] = email

                update[
                    "email_confidence"
                ] = data.get(
                    "email_confidence",
                    0,
                )
'''

count = source.count(old)

if count != 2:
    raise RuntimeError(
        f"Expected exactly 2 email persistence blocks, found {count}."
    )

patched = source.replace(old, new)

ast.parse(patched.lstrip("\ufeff"))

backup = Path(r".\backend\app\tasks.py.bak-email-persistence-v1")

if not backup.exists():
    backup.write_text(source, encoding="utf-8")

path.write_text(patched, encoding="utf-8")

print("tasks.py email persistence patched successfully.")
