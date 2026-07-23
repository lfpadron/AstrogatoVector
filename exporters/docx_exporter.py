"""Backward-compatible DOCX export wrapper."""

from __future__ import annotations

from exporters.final_package_exporter import FinalPackageExporter
from schemas.deliverable_models import FinalDeliverablePackage


def export_docx(report: dict) -> bytes:
    """Build a DOCX report from a final deliverable package payload."""
    package = FinalDeliverablePackage.model_validate(report)
    return FinalPackageExporter().export_docx(package)
