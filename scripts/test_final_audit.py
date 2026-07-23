"""Run final LinkedIn and ATS audit with fictitious local data."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.examples import (  # noqa: E402
    build_example_compatibility_report,
    build_example_linkedin_profile,
    build_example_market_analysis,
    build_example_professional_profile,
)
from services.final_audit_service import FinalAuditService, build_final_audit_fingerprint  # noqa: E402


def main() -> None:
    """Generate a final audit report using reproducible fictitious fixtures."""
    profile = build_example_professional_profile()
    market = build_example_market_analysis()
    linkedin = build_example_linkedin_profile()
    compatibility = build_example_compatibility_report()

    report = FinalAuditService().generate_report(profile, market, linkedin, compatibility)
    fingerprint = build_final_audit_fingerprint(profile, market, linkedin, compatibility)

    print(f"success={report.success}")
    print(f"linkedin_score={report.linkedin_positioning.score if report.linkedin_positioning else 'N/D'}")
    print(f"ats_score={report.ats_estimation.score if report.ats_estimation else 'N/D'}")
    print(f"overall_score={report.overall_score if report.overall_score is not None else 'N/D'}")
    print(f"findings={len(report.findings)}")
    print(f"quick_wins={len(report.quick_wins)}")
    print(f"fingerprint={fingerprint}")
    if report.executive_summary:
        print(report.executive_summary)


if __name__ == "__main__":
    main()
