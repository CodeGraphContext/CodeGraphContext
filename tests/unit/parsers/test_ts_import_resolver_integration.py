"""
Integration tests for TypeScript import resolution using the real TS parser
and the sample_project_typescript fixture with tsconfig paths.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager
from codegraphcontext.tools.languages.typescript import TypescriptTreeSitterParser
from codegraphcontext.tools.ts_import_resolver import (
    resolve_ts_import,
    parse_tsconfig_paths,
)


@pytest.fixture(scope="module")
def ts_parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "typescript"
    wrapper.language = manager.get_language_safe("typescript")
    wrapper.parser = manager.create_parser("typescript")
    return TypescriptTreeSitterParser(wrapper)


@pytest.fixture(scope="module")
def project_root():
    return (
        Path(__file__).parent.parent.parent
        / "fixtures"
        / "sample_projects"
        / "sample_project_typescript"
    )


@pytest.fixture(scope="module")
def ts_config(project_root):
    base_url, paths_map = parse_tsconfig_paths(project_root)
    return {
        "project_root": project_root.resolve(),
        "base_url": base_url,
        "paths_map": paths_map,
    }


class TestParseTsconfigFromFixture:
    """Verify tsconfig.json in the fixture is parsed correctly."""

    def test_base_url_resolved(self, ts_config, project_root):
        assert ts_config["base_url"] == project_root.resolve()

    def test_paths_map_loaded(self, ts_config):
        pm = ts_config["paths_map"]
        assert "@utils/*" in pm
        assert "@models/*" in pm
        assert "@shared/*" in pm
        assert "@app/*" in pm
        assert pm["@utils/*"] == ["src/utils/*"]
        assert pm["@models/*"] == ["src/models/*"]
        assert pm["@shared/*"] == ["src/shared/*"]
        assert pm["@app/*"] == ["src/*"]


class TestResolveImportsFromParsedFile:
    """Parse app-service.ts with the real TS parser and resolve each import."""

    @pytest.fixture(scope="class")
    def parsed_imports(self, ts_parser, project_root):
        app_service = project_root / "src" / "app-service.ts"
        result = ts_parser.parse(str(app_service))
        return result["imports"]

    def test_parser_finds_imports(self, parsed_imports):
        sources = {imp["source"] for imp in parsed_imports}
        assert "@utils/string-helpers" in sources
        assert "@utils/math-helpers" in sources
        assert "@models/user-model" in sources
        assert "@shared/constants" in sources
        assert "@shared/logger" in sources
        assert "./types-interfaces" in sources
        assert "./utilities-helpers" in sources
        assert "reflect-metadata" in sources

    def test_alias_utils_string_helpers_resolves(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@utils/string-helpers",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "utils" / "string-helpers.ts").resolve())
        assert result == expected

    def test_alias_utils_math_helpers_resolves(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@utils/math-helpers",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "utils" / "math-helpers.ts").resolve())
        assert result == expected

    def test_alias_models_user_model_resolves(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@models/user-model",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "models" / "user-model.ts").resolve())
        assert result == expected

    def test_alias_shared_constants_resolves(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@shared/constants",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "shared" / "constants.ts").resolve())
        assert result == expected

    def test_alias_shared_logger_resolves(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@shared/logger",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "shared" / "logger.ts").resolve())
        assert result == expected

    def test_relative_import_resolves(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "./types-interfaces",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "types-interfaces.ts").resolve())
        assert result == expected

    def test_relative_import_utilities_resolves(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "./utilities-helpers",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "utilities-helpers.ts").resolve())
        assert result == expected

    def test_bare_specifier_returns_none(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "reflect-metadata",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        assert result is None


class TestResolveExistingRelativeImports:
    """Verify that the existing relative imports in index.ts also resolve correctly."""

    def test_index_ts_imports_resolve(self, ts_config, project_root):
        importing_file = project_root / "src" / "index.ts"
        modules = [
            "types-interfaces",
            "classes-inheritance",
            "functions-generics",
            "async-promises",
            "decorators-metadata",
            "modules-namespaces",
            "advanced-types",
            "error-validation",
            "utilities-helpers",
        ]
        for mod in modules:
            result = resolve_ts_import(
                f"./{mod}",
                importing_file,
                ts_config["project_root"],
                base_url=ts_config["base_url"],
                paths_map=ts_config["paths_map"],
            )
            expected = str((project_root / "src" / f"{mod}.ts").resolve())
            assert result == expected, f"Failed to resolve ./{mod}"


class TestAppAlias:
    """Test the @app/* alias that maps to src/*."""

    def test_app_alias_resolves_to_src_file(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@app/types-interfaces",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "types-interfaces.ts").resolve())
        assert result == expected

    def test_app_alias_resolves_utils_index(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@app/utils",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        expected = str((project_root / "src" / "utils" / "index.ts").resolve())
        assert result == expected

    def test_app_alias_nonexistent_returns_none(self, ts_config, project_root):
        importing_file = project_root / "src" / "app-service.ts"
        result = resolve_ts_import(
            "@app/does-not-exist",
            importing_file,
            ts_config["project_root"],
            base_url=ts_config["base_url"],
            paths_map=ts_config["paths_map"],
        )
        assert result is None
