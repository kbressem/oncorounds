"""Helpers to load JSON schemas shipped with the repository."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_DIR = _ROOT / "schemas"


@lru_cache(maxsize=None)
def load_schema(schema_name: str) -> dict:
    """Return the parsed JSON schema stored under ``schemas/``."""
    if not schema_name.endswith(".json"):
        schema_name = f"{schema_name}.json"
    schema_path = _SCHEMA_DIR / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file {schema_path} not found.")
    with schema_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
