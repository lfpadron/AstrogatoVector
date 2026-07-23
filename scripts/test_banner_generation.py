"""Render fictitious LinkedIn banner previews safely in memory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from schemas.banner_models import LINKEDIN_BANNER_HEIGHT, LINKEDIN_BANNER_WIDTH, BannerRenderInput  # noqa: E402
from schemas.enums import OutputLanguage  # noqa: E402
from services.banner_audit_service import audit_banner_result  # noqa: E402
from services.banner_service import BANNER_TEMPLATES, BannerService  # noqa: E402

FICTITIOUS_PRIMARY = "Liderazgo de Proyectos y Transformación Digital"
FICTITIOUS_SPECIALTY = "Project Management · Gestión de Riesgos · Inteligencia Artificial"
FICTITIOUS_SUPPORTING = "Tecnología · Negocio · Equipos multidisciplinarios"
PREVIEW_DIR = PROJECT_ROOT / "tmp" / "banner_previews"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local fictitious LinkedIn banner rendering tests.")
    parser.add_argument("--save-preview", action="store_true", help="Save fictitious PNG previews under tmp/banner_previews/.")
    args = parser.parse_args()

    service = BannerService()
    failures = 0
    saved_paths: list[Path] = []

    if args.save_preview:
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    for template_id in BANNER_TEMPLATES:
        result = service.render_banner(
            BannerRenderInput(
                primary_line=FICTITIOUS_PRIMARY,
                specialty_line=FICTITIOUS_SPECIALTY,
                supporting_line=FICTITIOUS_SUPPORTING,
                visual_concept="Geometría vectorial mínima con nodos discretos.",
                template_id=template_id,
                output_language=OutputLanguage.ES,
            )
        )
        audit = audit_banner_result(result)
        status = "OK" if audit.passed else "FAILED"
        warning_count = len(result.warnings)
        print(
            f"{template_id}: {status} "
            f"{result.width}x{result.height} "
            f"contrast={audit.contrast_valid} "
            f"safe_zone={audit.safe_zone_valid} "
            f"overflow={audit.overflow_valid} "
            f"warnings={warning_count}"
        )
        if not audit.passed:
            failures += 1
            for finding in audit.findings:
                print(f"  - {finding}")
            for error in result.errors:
                print(f"  - {error}")
            continue
        if args.save_preview and result.image_bytes:
            output_path = PREVIEW_DIR / f"banner-{template_id}.png"
            output_path.write_bytes(result.image_bytes)
            saved_paths.append(output_path)

    print(f"Templates generated: {len(BANNER_TEMPLATES) - failures}/{len(BANNER_TEMPLATES)}")
    print(f"Expected dimensions: {LINKEDIN_BANNER_WIDTH}x{LINKEDIN_BANNER_HEIGHT}")
    if saved_paths:
        print("Saved fictitious previews:")
        for path in saved_paths:
            print(f"  {path}")
    else:
        print("Saved previews: none")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
