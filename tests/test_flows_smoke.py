"""
Flow smoke tests.

Basic tests to verify flows can be imported and have expected structure.
Does NOT execute flows - just checks they're properly defined.
"""
import importlib
import inspect
from pathlib import Path

import pytest


# All flow modules that should be importable
FLOW_MODULES = [
    'flows.handshake_flow',
    'flows.treasure_map_flow',
    'flows.corn_harvest_flow',
    'flows.gold_coin_flow',
    'flows.harvest_box_flow',
    'flows.iron_bar_flow',
    'flows.gem_flow',
    'flows.cabbage_flow',
    'flows.equipment_enhancement_flow',
    'flows.elite_zombie_flow',
    'flows.afk_rewards_flow',
    'flows.union_gifts_flow',
    'flows.union_technology_flow',
    'flows.hero_upgrade_arms_race_flow',
    'flows.stamina_claim_flow',
    'flows.stamina_use_flow',
    'flows.soldier_training_flow',
    'flows.soldier_upgrade_flow',
    'flows.rally_join_flow',
    'flows.healing_flow',
    'flows.bag_flow',
    'flows.gift_box_flow',
    'flows.tavern_quest_flow',
    'flows.faction_trials_flow',
    'flows.royal_city_flow',
    'flows.go_to_mark_flow',
]


class TestFlowImports:
    """Test that all flows can be imported without errors."""

    @pytest.mark.parametrize("module_name", FLOW_MODULES)
    def test_flow_imports(self, module_name):
        """Test that flow module can be imported."""
        try:
            module = importlib.import_module(module_name)
            assert module is not None
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")


class TestFlowStructure:
    """Test that flows have expected structure."""

    # Flows that should have a main function matching their name
    FLOW_FUNCTIONS = [
        ('flows.handshake_flow', 'handshake_flow'),
        ('flows.treasure_map_flow', 'treasure_map_flow'),
        ('flows.corn_harvest_flow', 'corn_harvest_flow'),
        ('flows.elite_zombie_flow', 'elite_zombie_flow'),
        ('flows.healing_flow', 'healing_flow'),
        ('flows.bag_flow', 'bag_flow'),
    ]

    @pytest.mark.parametrize("module_name,func_name", FLOW_FUNCTIONS)
    def test_flow_has_main_function(self, module_name, func_name):
        """Test that flow module has its main function."""
        try:
            module = importlib.import_module(module_name)
            assert hasattr(module, func_name), f"{module_name} missing function: {func_name}"
            func = getattr(module, func_name)
            assert callable(func), f"{module_name}.{func_name} is not callable"
        except ImportError:
            pytest.skip(f"Could not import {module_name}")

    @pytest.mark.parametrize("module_name,func_name", FLOW_FUNCTIONS)
    def test_flow_accepts_adb_parameter(self, module_name, func_name):
        """Test that flow function accepts an adb parameter."""
        try:
            module = importlib.import_module(module_name)
            if not hasattr(module, func_name):
                pytest.skip(f"{module_name} missing {func_name}")

            func = getattr(module, func_name)
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())

            # Should have at least one parameter (usually 'adb')
            assert len(params) >= 1, f"{module_name}.{func_name} should accept at least one parameter"
        except ImportError:
            pytest.skip(f"Could not import {module_name}")


class TestFlowsDirectory:
    """Test the flows directory structure."""

    @pytest.fixture
    def flows_dir(self):
        return Path(__file__).parent.parent / "scripts" / "flows"

    def test_flows_directory_exists(self, flows_dir):
        """Test that flows directory exists."""
        assert flows_dir.exists(), "scripts/flows directory does not exist"

    def test_flows_has_init(self, flows_dir):
        """Test that flows directory has __init__.py."""
        init_file = flows_dir / "__init__.py"
        assert init_file.exists(), "scripts/flows/__init__.py does not exist"

    def test_flow_files_are_python(self, flows_dir):
        """Test that all flow files are .py files."""
        flow_files = list(flows_dir.glob("*_flow.py"))
        assert len(flow_files) > 0, "No flow files found in scripts/flows"

        for flow_file in flow_files:
            assert flow_file.suffix == ".py", f"Flow file is not .py: {flow_file.name}"


class TestUtilsImports:
    """Test that required utils can be imported."""

    UTILS = [
        'utils.adb_helper',
        'utils.windows_screenshot_helper',
        'utils.view_state_detector',
        'utils.template_matcher',
        'utils.back_button_matcher',
        'utils.return_to_base_view',
        'utils.ocr_client',
    ]

    @pytest.mark.parametrize("module_name", UTILS)
    def test_utils_imports(self, module_name):
        """Test that utility module can be imported."""
        try:
            module = importlib.import_module(module_name)
            assert module is not None
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
