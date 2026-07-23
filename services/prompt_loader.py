"""Safe prompt file loading for OpenAI calls."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class PromptLoadError(Exception):
    """Raised when a prompt file cannot be safely loaded."""


def load_prompt(filename: str, *, base_dir: Path = PROMPTS_DIR) -> str:
    """Load a non-empty UTF-8 prompt from the configured prompts directory."""
    candidate = Path(filename)
    if candidate.is_absolute() or candidate.name != filename or ".." in candidate.parts:
        raise PromptLoadError("El nombre del prompt no está permitido.")

    base_path = base_dir.resolve()
    prompt_path = (base_path / filename).resolve()
    try:
        prompt_path.relative_to(base_path)
    except ValueError as exc:
        raise PromptLoadError("El prompt está fuera del directorio permitido.") from exc

    if not prompt_path.is_file():
        raise PromptLoadError("El archivo de prompt no existe.")

    text = prompt_path.read_text(encoding="utf-8")
    if not text.strip():
        raise PromptLoadError("El archivo de prompt está vacío.")

    return text.strip()
