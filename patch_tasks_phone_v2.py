from pathlib import Path
import ast

path = Path(r".\backend\app\tasks.py")
backup = Path(r".\backend\app\tasks.py.bak-phone-v2")

original = path.read_text(encoding="utf-8")

if not backup.exists():
    backup.write_text(original, encoding="utf-8")

if 'update["phone"]' in original or 'row["phone"]' in original:
    raise RuntimeError(
        "Phone persistence patch appears to already exist; refusing duplicate patch."
    )


def get_function_span(source: str, predicate):
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    for node in tree.body:
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        start_candidates = [node.lineno]

        start_candidates.extend(
            decorator.lineno
            for decorator in node.decorator_list
        )

        start = min(start_candidates) - 1
        end = node.end_lineno

        chunk = "".join(lines[start:end])

        if predicate(node, chunk):
            return start, end, chunk

    return None


def replace_once(
    chunk: str,
    old: str,
    new: str,
    label: str,
) -> str:
    count = chunk.count(old)

    if count != 1:
        raise RuntimeError(
            f"{label}: expected 1 match, found {count}."
        )

    return chunk.replace(old, new, 1)


def replace_function(
    source: str,
    start: int,
    end: int,
    new_chunk: str,
) -> str:
    lines = source.splitlines(keepends=True)

    return "".join(
        lines[:start]
        + [new_chunk]
        + lines[end:]
    )


# ============================================================
# 1. Earlier scrape/enrichment path
# ============================================================

early = get_function_span(
    original,
    lambda node, chunk: (
        "enrich = enrich_prospect(" in chunk
        and 'row["email"] = email' in chunk
        and 'row["email_confidence"]' in chunk
    ),
)

if not early:
    raise RuntimeError(
        "Could not locate earlier scrape/enrichment function."
    )

start, end, chunk = early

old_early = '''    if email:

        row["email"] = email

        row["email_confidence"] = (
            enrich.get(
                "email_confidence",
                0,
            )
        )
'''

new_early = '''    if email:

        row["email"] = email

        row["email_confidence"] = (
            enrich.get(
                "email_confidence",
                0,
            )
        )

    phone = (
        enrich.get(
            "phone"
        )
        or ""
    ).strip()

    if phone:
        row["phone"] = phone
'''

chunk = replace_once(
    chunk,
    old_early,
    new_early,
    "Earlier scrape/enrichment phone persistence",
)

source = replace_function(
    original,
    start,
    end,
    chunk,
)


# ============================================================
# 2. Manual enrichment task
# ============================================================

manual = get_function_span(
    source,
    lambda node, chunk: (
        node.name == "enrich_prospects_task"
    ),
)

if not manual:
    raise RuntimeError(
        "Could not locate enrich_prospects_task()."
    )

start, end, chunk = manual


# Add phone metadata.
old_meta = '''            meta[
                "email_candidates"
            ] = data.get(
                "email_candidates",
                [],
            )
'''

new_meta = '''            meta[
                "email_candidates"
            ] = data.get(
                "email_candidates",
                [],
            )

            meta[
                "phone_source"
            ] = data.get(
                "phone_source"
            )

            meta[
                "phone_candidates"
            ] = data.get(
                "phone_candidates",
                [],
            )

            meta[
                "phone_confidence"
            ] = data.get(
                "phone_confidence",
                0,
            )
'''

chunk = replace_once(
    chunk,
    old_meta,
    new_meta,
    "Manual enrichment phone metadata",
)


# Persist phone in prospects.phone.
old_manual_email = '''            if (
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

new_manual_email = '''            if (
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

            phone = (
                data.get(
                    "phone"
                )
                or ""
            ).strip()

            if phone:
                update[
                    "phone"
                ] = phone
'''

chunk = replace_once(
    chunk,
    old_manual_email,
    new_manual_email,
    "Manual enrichment phone column persistence",
)


# Phone-only enrichment counts as enriched.
old_count = '''            if (
                email
                or data.get(
                    "company_domain"
                )
            ):

                enriched += 1
'''

new_count = '''            if (
                email
                or phone
                or data.get(
                    "company_domain"
                )
            ):

                enriched += 1
'''

chunk = replace_once(
    chunk,
    old_count,
    new_count,
    "Manual enrichment counter",
)

source = replace_function(
    source,
    start,
    end,
    chunk,
)


# ============================================================
# 3. Automatic enrichment task
# ============================================================

auto = get_function_span(
    source,
    lambda node, chunk: (
        node.name == "auto_enrich_new_prospects_task"
    ),
)

if not auto:
    raise RuntimeError(
        "Could not locate auto_enrich_new_prospects_task()."
    )

start, end, chunk = auto


# Select phone and website.
old_select = '''        .select(
            "id, username, display_name, "
            "comment_text, bio_text, profile_url, "
            "post_url, email, metadata, status"
        )
'''

new_select = '''        .select(
            "id, username, display_name, "
            "comment_text, bio_text, profile_url, "
            "post_url, email, phone, website, "
            "metadata, status"
        )
'''

chunk = replace_once(
    chunk,
    old_select,
    new_select,
    "Automatic enrichment SELECT",
)


# Add phone metadata.
chunk = replace_once(
    chunk,
    old_meta,
    new_meta,
    "Automatic enrichment phone metadata",
)


# Persist phone.
old_auto_email = '''                update[
                    "email_confidence"
                ] = data.get(
                    "email_confidence",
                    0,
                )

                if prospect.get(
                    "status"
                ) in (
                    "new",
                    "scored",
                ):

                    update[
                        "status"
                    ] = "enriched"
'''

new_auto_email = '''                update[
                    "email_confidence"
                ] = data.get(
                    "email_confidence",
                    0,
                )

                if prospect.get(
                    "status"
                ) in (
                    "new",
                    "scored",
                ):

                    update[
                        "status"
                    ] = "enriched"

            phone = (
                data.get(
                    "phone"
                )
                or ""
            ).strip()

            if phone:
                update[
                    "phone"
                ] = phone

                if prospect.get(
                    "status"
                ) in (
                    "new",
                    "scored",
                ):

                    update[
                        "status"
                    ] = "enriched"
'''

chunk = replace_once(
    chunk,
    old_auto_email,
    new_auto_email,
    "Automatic enrichment phone column persistence",
)


# Phone-only enrichment counts as enriched.
chunk = replace_once(
    chunk,
    old_count,
    new_count,
    "Automatic enrichment counter",
)

source = replace_function(
    source,
    start,
    end,
    chunk,
)


# ============================================================
# 4. Validate before writing
# ============================================================

ast.parse(source)

required = [
    'row["phone"] = phone',
    'update[\n                    "phone"\n                ] = phone',
    '"phone_source"',
    '"phone_candidates"',
    '"phone_confidence"',
    '"post_url, email, phone, website, "',
]

for required_text in required:
    if required_text not in source:
        raise RuntimeError(
            "Validation failed; missing expected text: "
            + required_text
        )


path.write_text(
    source,
    encoding="utf-8",
)

print(
    "tasks.py phone persistence patch applied successfully."
)
