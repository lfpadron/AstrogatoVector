from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.editorial_plan_models import EditorialCalendar, EditorialCalendarWeek
from tests.editorial_plan_helpers import build_editorial_plan


def test_professional_brand_plan_requires_four_weeks_and_twelve_posts():
    plan = build_editorial_plan()

    assert len(plan.calendar.weeks) == 4
    assert len(plan.calendar.posts) == 12
    assert {post.day for post in plan.calendar.posts[:3]} == {"monday", "wednesday", "friday"}


def test_editorial_calendar_rejects_consecutive_equal_themes():
    plan = build_editorial_plan()
    posts = list(plan.calendar.posts)
    posts[1] = posts[1].model_copy(update={"theme": posts[0].theme})
    weeks = [
        EditorialCalendarWeek(week=week, posts=[post for post in posts if post.week == week])
        for week in range(1, 5)
    ]

    with pytest.raises(ValidationError):
        EditorialCalendar(weeks=weeks)
