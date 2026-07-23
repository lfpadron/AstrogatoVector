from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from schemas.evidence_models import CandidateProfessionalProfile
from schemas.examples import build_example_application_result
from schemas.result_models import ApplicationResult


def test_application_result_complete_valid():
    result = build_example_application_result()

    assert isinstance(result, ApplicationResult)
    assert result.schema_version == "1.0"


def test_application_result_serializes_json():
    result = build_example_application_result()
    payload = json.loads(result.model_dump_json())

    assert payload["schema_version"] == "1.0"


def test_application_result_json_schema_is_object():
    schema = ApplicationResult.model_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False


def test_structured_output_schema_for_professional_profile_is_object():
    schema = CandidateProfessionalProfile.model_json_schema()

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert "$defs" in schema


def test_application_result_round_trip():
    result = build_example_application_result()
    restored = ApplicationResult.model_validate(result.model_dump())

    assert restored == result


def test_application_result_rejects_unknown_fields():
    data = build_example_application_result().model_dump()
    data["unexpected"] = "nope"

    with pytest.raises(ValidationError):
        ApplicationResult.model_validate(data)
