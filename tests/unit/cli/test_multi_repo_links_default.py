"""MULTI_REPO_LINKS feature flag: non-breaking default (PR #1).

The flag gates the wire-coupling extractor family added by later PRs. PR #1
only lands the schema surface and this default. The invariant this file
protects: an upgrade from CGC 0.6.13 to the next release MUST NOT change any
observable behavior for a user who has not opted in.
"""

from codegraphcontext.cli.config_manager import (
    CONFIG_DESCRIPTIONS,
    CONFIG_VALIDATORS,
    DEFAULT_CONFIG,
)
from codegraphcontext.tools.indexing import schema_contract as sc


class TestMultiRepoLinksDefault:
    def test_flag_key_is_registered(self):
        assert "MULTI_REPO_LINKS" in DEFAULT_CONFIG

    def test_flag_defaults_to_false(self):
        """Default 'false' is the entire non-breaking-upgrade contract."""
        assert DEFAULT_CONFIG["MULTI_REPO_LINKS"] == "false"

    def test_flag_accepts_only_bool_strings(self):
        assert CONFIG_VALIDATORS["MULTI_REPO_LINKS"] == ["true", "false"]

    def test_flag_has_user_facing_description(self):
        desc = CONFIG_DESCRIPTIONS.get("MULTI_REPO_LINKS", "")
        assert "wire-coupling" in desc.lower() or "multi-repo" in desc.lower()
        assert "false" in desc.lower(), "description must call out the default"

    def test_schema_and_config_agree_on_flag_name(self):
        assert sc.MULTI_REPO_LINKS_FLAG == "MULTI_REPO_LINKS"
        assert sc.MULTI_REPO_LINKS_FLAG in DEFAULT_CONFIG
        assert sc.MULTI_REPO_LINKS_FLAG in CONFIG_VALIDATORS
        assert sc.MULTI_REPO_LINKS_FLAG in CONFIG_DESCRIPTIONS
