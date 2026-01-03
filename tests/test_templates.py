"""
Template verification tests.

Verifies that all required templates exist and have valid dimensions.
Also checks that mask pairs exist (template + mask).
"""
import os
from pathlib import Path

import pytest

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth"


class TestTemplateExistence:
    """Test that all required templates exist."""

    # Core icon matcher templates
    ICON_TEMPLATES = [
        'handshake_icon_4k.png',
        'treasure_map_4k.png',
        'corn_harvest_bubble_4k.png',
        'gold_coin_tight_4k.png',
        'harvest_box_4k.png',
        'iron_bar_tight_4k.png',
        'gem_tight_4k.png',
        'cabbage_tight_4k.png',
        'sword_tight_4k.png',
        'dog_house_4k.png',
        'chest_timer_4k.png',
    ]

    # Back button templates
    BACK_BUTTON_TEMPLATES = [
        'back_button_4k.png',
        'back_button_light_4k.png',
        'back_button_union_4k.png',
    ]

    # View state detector templates
    VIEW_STATE_TEMPLATES = [
        'world_button_4k.png',
        'town_button_4k.png',
        'town_button_zoomed_out_4k.png',
        'world_button_shaded_4k.png',
        'world_button_shaded_dark_4k.png',
    ]

    # Barracks state templates
    BARRACKS_TEMPLATES = [
        'stopwatch_barrack_4k.png',
        'white_soldier_barrack_4k.png',
        'yellow_soldier_barrack_4k.png',
        'yellow_soldier_barrack_v2_4k.png',
        'yellow_soldier_barrack_v3_4k.png',
        'yellow_soldier_barrack_v4_4k.png',
        'yellow_soldier_barrack_v5_4k.png',
        'yellow_soldier_barrack_v6_4k.png',
    ]

    @pytest.fixture
    def template_dir(self):
        return TEMPLATE_DIR

    @pytest.mark.parametrize("template", ICON_TEMPLATES)
    def test_icon_templates_exist(self, template_dir, template):
        """Test that icon matcher templates exist."""
        path = template_dir / template
        assert path.exists(), f"Missing icon template: {template}"

    @pytest.mark.parametrize("template", BACK_BUTTON_TEMPLATES)
    def test_back_button_templates_exist(self, template_dir, template):
        """Test that back button templates exist."""
        path = template_dir / template
        assert path.exists(), f"Missing back button template: {template}"

    @pytest.mark.parametrize("template", VIEW_STATE_TEMPLATES)
    def test_view_state_templates_exist(self, template_dir, template):
        """Test that view state detector templates exist."""
        path = template_dir / template
        assert path.exists(), f"Missing view state template: {template}"

    @pytest.mark.parametrize("template", BARRACKS_TEMPLATES)
    def test_barracks_templates_exist(self, template_dir, template):
        """Test that barracks state templates exist."""
        path = template_dir / template
        assert path.exists(), f"Missing barracks template: {template}"


class TestMaskPairs:
    """Test that templates with masks have corresponding mask files."""

    # Templates that should have masks (CCORR matching)
    MASKED_TEMPLATES = [
        'back_button_union_4k.png',
        'corn_harvest_bubble_4k.png',
        'gold_coin_tight_4k.png',
        'iron_bar_tight_4k.png',
        'gem_tight_4k.png',
    ]

    @pytest.fixture
    def template_dir(self):
        return TEMPLATE_DIR

    @pytest.mark.parametrize("template", MASKED_TEMPLATES)
    def test_mask_pairs_exist(self, template_dir, template):
        """Test that masked templates have corresponding mask files."""
        # Template exists
        template_path = template_dir / template
        assert template_path.exists(), f"Missing template: {template}"

        # Mask file should exist
        mask_name = template.replace('_4k.png', '_mask_4k.png')
        mask_path = template_dir / mask_name
        assert mask_path.exists(), f"Missing mask for {template}: {mask_name}"


class TestTemplateSizes:
    """Test that templates have reasonable dimensions."""

    @pytest.fixture
    def template_dir(self):
        return TEMPLATE_DIR

    def test_templates_not_empty(self, template_dir):
        """Test that all templates have non-zero size."""
        import cv2

        for template_file in template_dir.glob("*.png"):
            img = cv2.imread(str(template_file))
            assert img is not None, f"Could not read template: {template_file.name}"
            h, w = img.shape[:2]
            assert h > 0 and w > 0, f"Template has zero dimensions: {template_file.name}"
            assert h < 3000 and w < 3000, f"Template suspiciously large: {template_file.name} ({w}x{h})"

    def test_mask_sizes_match_templates(self, template_dir):
        """Test that mask files have same dimensions as their templates."""
        import cv2

        for mask_file in template_dir.glob("*_mask_4k.png"):
            # Find corresponding template
            template_name = mask_file.name.replace('_mask_4k.png', '_4k.png')
            template_path = template_dir / template_name

            if template_path.exists():
                mask = cv2.imread(str(mask_file))
                template = cv2.imread(str(template_path))

                assert mask is not None, f"Could not read mask: {mask_file.name}"
                assert template is not None, f"Could not read template: {template_name}"

                mask_h, mask_w = mask.shape[:2]
                temp_h, temp_w = template.shape[:2]

                assert mask_h == temp_h and mask_w == temp_w, \
                    f"Mask size mismatch for {template_name}: template={temp_w}x{temp_h}, mask={mask_w}x{mask_h}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
