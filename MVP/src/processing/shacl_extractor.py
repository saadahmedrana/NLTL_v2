import re


def extract_shacl_block(raw_text: str) -> str:
    pattern = re.compile(r"<BEGIN_SHACL>\s*(.*?)\s*<END_SHACL>", re.DOTALL)
    match = pattern.search(raw_text)
    if not match:
        raise ValueError("Could not find <BEGIN_SHACL> ... <END_SHACL> block in generator output.")
    return match.group(1).strip()