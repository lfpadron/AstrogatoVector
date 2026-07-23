from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.examples import build_example_candidate_input
from schemas.input_models import CandidateInput


def test_candidate_input_valid():
    candidate = build_example_candidate_input()

    assert isinstance(candidate, CandidateInput)
    assert len(candidate.jobs) == 2


def test_candidate_input_one_job_fails():
    data = build_example_candidate_input().model_dump()
    data["jobs"] = data["jobs"][:1]

    with pytest.raises(ValidationError):
        CandidateInput.model_validate(data)


def test_candidate_input_seven_jobs_fails():
    data = build_example_candidate_input().model_dump()
    template = data["jobs"][0].copy()
    data["jobs"] = [{**template, "index": index, "title": f"Vacante {index}"} for index in range(1, 8)]

    with pytest.raises(ValidationError):
        CandidateInput.model_validate(data)


def test_candidate_input_duplicate_indices_fail():
    data = build_example_candidate_input().model_dump()
    data["jobs"][1]["index"] = 1

    with pytest.raises(ValidationError):
        CandidateInput.model_validate(data)


def test_candidate_input_non_consecutive_indices_fail():
    data = build_example_candidate_input().model_dump()
    data["jobs"][1]["index"] = 3

    with pytest.raises(ValidationError):
        CandidateInput.model_validate(data)


def test_job_source_url_without_url_fails():
    data = build_example_candidate_input().model_dump()
    data["jobs"][0]["source"] = "url"
    data["jobs"][0]["url"] = None

    with pytest.raises(ValidationError):
        CandidateInput.model_validate(data)


def test_linkedin_generated_is_valid_without_text_or_url():
    data = build_example_candidate_input().model_dump()
    data["linkedin_source"] = "generated"
    data["linkedin_text"] = None
    data["linkedin_url"] = None

    candidate = CandidateInput.model_validate(data)

    assert candidate.linkedin_source == "generated"


def test_linkedin_text_without_text_fails():
    data = build_example_candidate_input().model_dump()
    data["linkedin_source"] = "text"
    data["linkedin_text"] = None

    with pytest.raises(ValidationError):
        CandidateInput.model_validate(data)
