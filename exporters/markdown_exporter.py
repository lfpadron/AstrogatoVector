"""Backward-compatible Markdown export wrapper."""

from __future__ import annotations

from exporters.final_package_exporter import FinalPackageExporter
from schemas.deliverable_models import FinalDeliverablePackage


def export_markdown(report: dict) -> str:
    """Build a Markdown report from a final deliverable package payload."""
    package = FinalDeliverablePackage.model_validate(report)
    return FinalPackageExporter().export_markdown(package).decode("utf-8")
