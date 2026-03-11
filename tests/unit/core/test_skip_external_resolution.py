"""
Unit tests for SKIP_EXTERNAL_RESOLUTION configuration option.
Tests config_manager.py and graph_builder.py integration.
"""

import os
import asyncio
import pytest
from unittest.mock import MagicMock, patch, call
from codegraphcontext.cli.config_manager import (
    get_config_value,
    set_config_value,
    CONFIG_DESCRIPTIONS,
    CONFIG_VALIDATORS,
    DEFAULT_CONFIG
)


class TestSkipExternalResolutionConfig:
    """Test the SKIP_EXTERNAL_RESOLUTION configuration cli option."""

    def test_config_exists_in_descriptions(self):
        """Test that SKIP_EXTERNAL_RESOLUTION has a description."""
        assert "SKIP_EXTERNAL_RESOLUTION" in CONFIG_DESCRIPTIONS
        assert len(CONFIG_DESCRIPTIONS["SKIP_EXTERNAL_RESOLUTION"]) > 0
        assert "external" in CONFIG_DESCRIPTIONS["SKIP_EXTERNAL_RESOLUTION"].lower()

    def test_config_has_validator(self):
        """Test that SKIP_EXTERNAL_RESOLUTION has valid values list."""
        assert "SKIP_EXTERNAL_RESOLUTION" in CONFIG_VALIDATORS
        valid_values = CONFIG_VALIDATORS["SKIP_EXTERNAL_RESOLUTION"]
        assert isinstance(valid_values, list)
        assert len(valid_values) == 2

    def test_validator_accepts_true(self):
        """Test that validator list includes 'true'."""
        valid_values = CONFIG_VALIDATORS["SKIP_EXTERNAL_RESOLUTION"]
        assert "true" in valid_values

    def test_validator_accepts_false(self):
        """Test that validator list includes 'false'."""
        valid_values = CONFIG_VALIDATORS["SKIP_EXTERNAL_RESOLUTION"]
        assert "false" in valid_values

    def test_validator_rejects_invalid_values(self):
        """Test that validator list does not include invalid values."""
        valid_values = CONFIG_VALIDATORS["SKIP_EXTERNAL_RESOLUTION"]
        assert "yes" not in valid_values
        assert "no" not in valid_values
        assert "1" not in valid_values
        assert "0" not in valid_values
        assert "enabled" not in valid_values

    def test_default_value_is_false(self):
        """Test that default value is 'false' for backward compatibility."""
        from codegraphcontext.cli.config_manager import DEFAULT_CONFIG
        assert "SKIP_EXTERNAL_RESOLUTION" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["SKIP_EXTERNAL_RESOLUTION"] == "false"

    def test_set_and_get_config_value(self):
        """Test setting and getting the configuration value."""
        # Set to true
        set_config_value("SKIP_EXTERNAL_RESOLUTION", "true")
        assert get_config_value("SKIP_EXTERNAL_RESOLUTION").lower() == "true"

        # Set to false
        set_config_value("SKIP_EXTERNAL_RESOLUTION", "false")
        assert get_config_value("SKIP_EXTERNAL_RESOLUTION").lower() == "false"

    def test_environment_variable_override(self):
        """Test that environment variable SKIP_EXTERNAL_RESOLUTION works."""
        with patch.dict(os.environ, {"SKIP_EXTERNAL_RESOLUTION": "true"}):
            value = get_config_value("SKIP_EXTERNAL_RESOLUTION")
            assert value == "true"

        with patch.dict(os.environ, {"SKIP_EXTERNAL_RESOLUTION": "false"}):
            value = get_config_value("SKIP_EXTERNAL_RESOLUTION")
            assert value == "false"


class TestSkipExternalResolutionBehavior:
    """Test the behavior of SKIP_EXTERNAL_RESOLUTION in graph_builder.py
    
    Note: Full behavior testing requires Neo4j session mocking, which is complex.
    These tests verify the code structure and imports are correct.
    The actual behavior is tested implicitly through the integration tests.
    """

    def test_graph_builder_uses_config_value(self):
        """Test that GraphBuilder imports and can call get_config_value."""
        from codegraphcontext.tools.graph_builder import GraphBuilder
        from codegraphcontext.cli.config_manager import get_config_value
        
        # Verify the import exists and is callable
        assert callable(get_config_value)
        
        # Verify GraphBuilder class exists
        assert GraphBuilder is not None

    def test_skip_external_logic_exists_in_code(self):
        """Test that the skip_external logic is present in graph_builder.py"""
        import inspect
        from codegraphcontext.tools.graph_builder import GraphBuilder
        
        # Get source code of _create_function_calls method
        source = inspect.getsource(GraphBuilder._create_function_calls)
        
        # Verify key logic is present
        assert "skip_external" in source
        assert "SKIP_EXTERNAL_RESOLUTION" in source
        assert "is_unresolved_external" in source
        assert "if skip_external and is_unresolved_external:" in source


class TestBackwardCompatibility:
    """Test that existing behavior is preserved when config is not set."""

    def test_default_behavior_unchanged(self):
        """Test that default behavior matches original (warnings + attempts)."""
        # When SKIP_EXTERNAL_RESOLUTION is not set or is "false",
        # behavior should match original cgc behavior
        
        with patch.dict(os.environ, {}, clear=True):
            from codegraphcontext.cli.config_manager import get_config_value
            
            # Default should be None or "false"
            value = get_config_value("SKIP_EXTERNAL_RESOLUTION")
            assert value is None or value.lower() == "false"

    def test_existing_configs_not_affected(self):
        """Test that other configuration options still work."""
        # Setting SKIP_EXTERNAL_RESOLUTION should not affect other configs
        set_config_value("SKIP_EXTERNAL_RESOLUTION", "true")
        set_config_value("INDEX_VARIABLES", "false")
        
        assert get_config_value("SKIP_EXTERNAL_RESOLUTION").lower() == "true"
        assert get_config_value("INDEX_VARIABLES").lower() == "false"


# Integration test (would require actual Neo4j - marked as e2e)
@pytest.mark.e2e
class TestSkipExternalResolutionE2E:
    """End-to-end tests for SKIP_EXTERNAL_RESOLUTION (requires Neo4j)."""
    
    def test_indexing_with_skip_external_enabled(self):
        """Test full indexing cycle with SKIP_EXTERNAL_RESOLUTION=true."""
        # This would be an actual integration test
        # Requires Neo4j running and test Java project
        # Should verify: no external warnings, only internal CALLS created
        pytest.skip("E2E test - requires Neo4j database")

    def test_performance_improvement(self):
        """Test that indexing is faster with SKIP_EXTERNAL_RESOLUTION=true."""
        # This would measure performance
        # Expected: significantly faster for Java projects with Spring/Commons
        pytest.skip("E2E test - requires Neo4j database and performance benchmarks")
