from __future__ import annotations

from components.linkedin_profile_flow import build_linkedin_profile_edit_state
from tests.linkedin_profile_helpers import build_linkedin_output


def test_edit_state_is_initialized_from_audited_output_without_mutating_it():
    output = build_linkedin_output()

    edit_state = build_linkedin_profile_edit_state(output)
    edit_state["headline"] = "Texto editado por usuario"

    assert edit_state["banner"]["primary_line"] == output.banner.primary_line
    assert edit_state["headline"] != output.headline.text
    assert output.headline.text == "Project Manager | Agile, Jira y stakeholder management"


def test_edit_state_contains_expected_copyable_sections():
    edit_state = build_linkedin_profile_edit_state(build_linkedin_output())

    assert set(edit_state) == {
        "edited",
        "banner",
        "headline",
        "about",
        "experience",
        "selected_skills",
        "selected_keywords",
    }
    assert edit_state["experience"][0]["rewritten_text"]
    assert "Agile" in edit_state["selected_skills"]
    assert "Kubernetes" in edit_state["selected_keywords"]
