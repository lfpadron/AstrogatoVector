"""Safe smoke test for LinkedIn profile generation with fictitious data."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.enums import OutputLanguage  # noqa: E402
from schemas.examples import build_example_market_analysis, build_example_professional_profile  # noqa: E402
from services.linkedin_profile_generation_service import LinkedInProfileGenerationService  # noqa: E402
from services.openai_config import OpenAIConfigurationError  # noqa: E402
from services.openai_service import create_openai_service  # noqa: E402


def main() -> int:
    """Run a safe profile generation check without printing raw prompts or full About text."""
    language = _language_arg(sys.argv[1:])
    try:
        service = LinkedInProfileGenerationService(create_openai_service())
    except OpenAIConfigurationError:
        print("LinkedIn profile generation: configuration incomplete")
        return 0

    result = service.generate_profile(
        build_example_professional_profile(),
        build_example_market_analysis(),
        language,
    )
    if not result.success or result.profile_output is None:
        print("LinkedIn profile generation: failed")
        print(f"category={result.error_category or 'unknown'} retryable={result.retryable}")
        print(result.user_message or "No safe message returned.")
        return 1 if not result.retryable else 0

    output = result.profile_output
    print("LinkedIn profile generation: OK")
    print(f"model={result.model_used or 'unknown'}")
    print(f"headline={output.headline.text}")
    print(f"headline_chars={output.headline.character_count}")
    print(f"about_chars={output.about.character_count}")
    print(f"experiences={len(output.experience)}")
    print(f"skills={len(output.prioritized_skills)}")
    print(f"ats_keywords={len(output.ats_keywords)}")
    print(f"audit_passed={result.audit_passed}")
    print(f"latency_ms={result.latency_ms}")
    print(f"tokens={result.total_tokens if result.total_tokens is not None else 'unknown'}")
    return 0


def _language_arg(args: list[str]) -> OutputLanguage:
    if len(args) >= 2 and args[0] == "--language":
        return OutputLanguage(args[1])
    return OutputLanguage.ES


if __name__ == "__main__":
    raise SystemExit(main())
