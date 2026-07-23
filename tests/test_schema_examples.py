from __future__ import annotations

import json

from schemas.examples import (
    build_example_application_result,
    build_example_candidate_input,
    build_example_communication_output,
    build_example_compatibility_report,
    build_example_content_plan,
    build_example_market_analysis,
    build_example_professional_profile,
)


def test_all_example_builders_generate_valid_models():
    examples = [
        build_example_candidate_input(),
        build_example_professional_profile(),
        build_example_market_analysis(),
        build_example_compatibility_report(),
        build_example_communication_output(),
        build_example_content_plan(),
        build_example_application_result(),
    ]

    for example in examples:
        assert example.model_dump()
        assert json.loads(example.model_dump_json())
        assert example.__class__.model_json_schema()["type"] == "object"


def test_examples_do_not_contain_sensitive_markers():
    payload = build_example_application_result().model_dump_json()
    forbidden = ["RFC", "CURP", "cuenta bancaria", "contraseña", "domicilio particular"]

    assert not any(marker.casefold() in payload.casefold() for marker in forbidden)
