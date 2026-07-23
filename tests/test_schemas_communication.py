from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.communication_models import CommunicationOutput
from schemas.examples import build_example_communication_output


def test_communication_cover_letters_valid():
    output = build_example_communication_output()

    assert len(output.cover_letters) == 2
    output.validate_for_job_indices([1, 2])


def test_communication_duplicate_letters_fail():
    data = build_example_communication_output().model_dump()
    data["cover_letters"][1]["job_index"] = 1

    with pytest.raises(ValidationError):
        CommunicationOutput.model_validate(data)


def test_communication_missing_expected_letter_fails_against_job_indices():
    output = build_example_communication_output()

    with pytest.raises(ValueError):
        output.validate_for_job_indices([1, 2, 3])
