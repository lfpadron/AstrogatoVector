from __future__ import annotations

import zipfile
from io import BytesIO

from exporters.targeted_cv_zip_exporter import TargetedCVZipExporter
from services.export_audit_service import ExportAuditService
from services.targeted_cv_ats_audit_service import audit_targeted_cv_ats
from services.targeted_cv_audit_service import audit_targeted_cv
from tests.targeted_cv_helpers import build_targeted_cv, build_targeted_cv_inputs


def test_targeted_cv_zip_export_contains_required_structure():
    profile, market, compatibility = build_targeted_cv_inputs()
    cv = build_targeted_cv(1)
    audit = audit_targeted_cv(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])
    ats = audit_targeted_cv_ats(cv, profile, market.job_analyses[0], compatibility.job_compatibilities[0])

    data = TargetedCVZipExporter().export([cv], audits={1: audit}, ats_audits={1: ats})

    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = set(archive.namelist())
    assert "targeted-cvs/README.txt" in names
    assert "targeted-cvs/manifest.json" in names
    assert "targeted-cvs/vacancy-01/cv.md" in names
    assert "targeted-cvs/vacancy-01/cv.docx" in names
    assert "targeted-cvs/vacancy-01/cv.pdf" in names
    assert "targeted-cvs/vacancy-01/review-summary.json" in names
    assert ExportAuditService().audit_targeted_cv_zip(data).passed
