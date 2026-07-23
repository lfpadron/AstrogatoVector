from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.enums import PriorityLevel, SkillCategory
from schemas.examples import build_example_market_analysis
from schemas.market_models import MarketKeyword, TargetMarketAnalysis


def test_market_keyword_frequency_correct():
    keyword = MarketKeyword(
        keyword="Stakeholder management",
        normalized_keyword="stakeholder management",
        frequency=2,
        job_indices=[1, 2],
        category=SkillCategory.COMMUNICATION,
        priority=PriorityLevel.HIGH,
    )

    assert keyword.frequency == 2


def test_market_keyword_frequency_inconsistent_fails():
    with pytest.raises(ValidationError):
        MarketKeyword(
            keyword="Stakeholder management",
            normalized_keyword="stakeholder management",
            frequency=1,
            job_indices=[1, 2],
            category=SkillCategory.COMMUNICATION,
            priority=PriorityLevel.HIGH,
        )


def test_target_market_two_job_analyses_valid():
    market = build_example_market_analysis()

    assert isinstance(market, TargetMarketAnalysis)
    assert len(market.job_analyses) == 2


def test_target_market_one_job_analysis_fails():
    data = build_example_market_analysis().model_dump()
    data["job_analyses"] = data["job_analyses"][:1]

    with pytest.raises(ValidationError):
        TargetMarketAnalysis.model_validate(data)
