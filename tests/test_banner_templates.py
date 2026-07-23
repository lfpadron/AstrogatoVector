from __future__ import annotations

import re

from schemas.banner_models import ALLOWED_BANNER_TEMPLATE_IDS, LINKEDIN_BANNER_HEIGHT, LINKEDIN_BANNER_WIDTH
from services.banner_service import BANNER_TEMPLATES, create_gradient_background, validate_contrast


def test_all_required_banner_templates_exist_with_valid_colors():
    assert set(BANNER_TEMPLATES) == set(ALLOWED_BANNER_TEMPLATE_IDS)

    for template_id, template in BANNER_TEMPLATES.items():
        assert template.template_id == template_id
        assert template.display_name
        assert template.decorative_style
        for color in (template.background_start, template.background_end, template.primary_text, template.secondary_text, template.accent):
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", color)
        assert validate_contrast(template) is True


def test_template_backgrounds_are_renderable_and_not_flat():
    for template in BANNER_TEMPLATES.values():
        image = create_gradient_background(
            LINKEDIN_BANNER_WIDTH,
            LINKEDIN_BANNER_HEIGHT,
            template.background_start,
            template.background_end,
        )

        assert image.size == (LINKEDIN_BANNER_WIDTH, LINKEDIN_BANNER_HEIGHT)
        assert image.getpixel((0, 0)) != image.getpixel((LINKEDIN_BANNER_WIDTH - 1, 0))
