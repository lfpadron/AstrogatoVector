"""Run the OpenAI diagnostic call from the command line."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.openai_config import OpenAIConfigurationError  # noqa: E402
from services.openai_service import create_openai_service  # noqa: E402


def main() -> int:
    """Run a safe diagnostic and print only non-secret metadata."""
    try:
        result = create_openai_service().run_diagnostic()
    except OpenAIConfigurationError:
        print("OpenAI diagnostic: configuration incomplete")
        return 0

    if result.success:
        print("OpenAI diagnostic: OK")
        print(f"Model: {result.model_used or 'unknown'}")
        print("Structured response: valid")
        print(f"Latency: {result.latency_ms if result.latency_ms is not None else 'unknown'} ms")
        return 0

    print("OpenAI diagnostic: FAILED")
    print(f"Model: {result.model_used or 'unknown'}")
    print(f"Category: {result.error_category or 'unknown'}")
    print(f"Retryable: {'yes' if result.retryable else 'no'}")
    print(result.user_message or "Ocurrió un error inesperado al comunicarse con OpenAI.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
