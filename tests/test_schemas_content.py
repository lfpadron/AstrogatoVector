from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.content_models import FourWeekContentPlan
from schemas.examples import build_example_content_plan


def test_four_week_content_plan_eight_posts_valid():
    plan = build_example_content_plan()

    assert len(plan.posts) == 8


def test_four_week_content_plan_seven_posts_fails():
    data = build_example_content_plan().model_dump()
    data["posts"] = data["posts"][:7]

    with pytest.raises(ValidationError):
        FourWeekContentPlan.model_validate(data)


def test_four_week_content_plan_missing_week_fails():
    data = build_example_content_plan().model_dump()
    for post in data["posts"]:
        if post["week"] == 4:
            post["week"] = 3

    with pytest.raises(ValidationError):
        FourWeekContentPlan.model_validate(data)


def test_four_week_content_plan_three_posts_in_week_fails():
    data = build_example_content_plan().model_dump()
    data["posts"][-1]["week"] = 3

    with pytest.raises(ValidationError):
        FourWeekContentPlan.model_validate(data)


def test_four_week_content_plan_repeated_combination_fails():
    data = build_example_content_plan().model_dump()
    data["posts"][1]["publication_number"] = 1

    with pytest.raises(ValidationError):
        FourWeekContentPlan.model_validate(data)
