"""Small Python helpers used while generating COMSOL Java source."""

import re


def comsol_safe_name(text: str) -> str:
    """Return a path/name string that is safe to embed in COMSOL Java strings."""
    return text.replace("\\", "/")


def safe_java_identifier(text: str) -> str:
    """Convert arbitrary case names into valid Java class identifiers."""
    identifier = re.sub(r"[^0-9a-zA-Z_]", "_", text)
    if not identifier:
        identifier = "comsol_case"
    if identifier[0].isdigit():
        identifier = f"case_{identifier}"
    return identifier


def chunk_list(items: list[str], size: int) -> list[list[str]]:
    """Split a list into fixed-size chunks while preserving order."""
    return [items[idx:idx + size] for idx in range(0, len(items), size)]
