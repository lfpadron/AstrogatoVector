"""Utilities for exporting Pydantic JSON Schema files."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


def export_model_json_schema(model_class: type[BaseModel], output_path: Path) -> None:
    """Export one Pydantic model JSON Schema to a file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = model_class.model_json_schema()
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
