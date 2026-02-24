import pytest
from pathlib import Path

from codegraphcontext.tools.ts_import_resolver import (
    _try_resolve_file,
    resolve_ts_import,
    parse_tsconfig_paths,
)


class TestTryResolveFile:
    def test_resolves_ts_extension(self, temp_test_dir):
        (temp_test_dir / "utils.ts").write_text("export const x = 1;")
        result = _try_resolve_file(temp_test_dir / "utils")
        assert result == str((temp_test_dir / "utils.ts").resolve())

    def test_resolves_tsx_extension(self, temp_test_dir):
        (temp_test_dir / "App.tsx").write_text("export default function App() {}")
        result = _try_resolve_file(temp_test_dir / "App")
        assert result == str((temp_test_dir / "App.tsx").resolve())

    def test_resolves_js_extension(self, temp_test_dir):
        (temp_test_dir / "helper.js").write_text("module.exports = {};")
        result = _try_resolve_file(temp_test_dir / "helper")
        assert result == str((temp_test_dir / "helper.js").resolve())

    def test_resolves_index_ts_in_directory(self, temp_test_dir):
        components_dir = temp_test_dir / "components"
        components_dir.mkdir()
        (components_dir / "index.ts").write_text("export {};")
        result = _try_resolve_file(components_dir)
        assert result == str((components_dir / "index.ts").resolve())

    def test_resolves_index_tsx_in_directory(self, temp_test_dir):
        components_dir = temp_test_dir / "components"
        components_dir.mkdir()
        (components_dir / "index.tsx").write_text("export {};")
        result = _try_resolve_file(components_dir)
        assert result == str((components_dir / "index.tsx").resolve())

    def test_ts_preferred_over_js(self, temp_test_dir):
        (temp_test_dir / "utils.ts").write_text("export {};")
        (temp_test_dir / "utils.js").write_text("module.exports = {};")
        result = _try_resolve_file(temp_test_dir / "utils")
        assert result == str((temp_test_dir / "utils.ts").resolve())

    def test_exact_path_with_extension(self, temp_test_dir):
        (temp_test_dir / "data.json").write_text("{}")
        result = _try_resolve_file(temp_test_dir / "data.json")
        assert result == str((temp_test_dir / "data.json").resolve())

    def test_nonexistent_returns_none(self, temp_test_dir):
        result = _try_resolve_file(temp_test_dir / "nonexistent")
        assert result is None


class TestResolveRelativeImports:
    def test_dot_slash_resolves(self, temp_test_dir):
        src = temp_test_dir / "src"
        src.mkdir()
        (src / "utils.ts").write_text("export {};")
        importing_file = src / "index.ts"
        importing_file.write_text("")

        result = resolve_ts_import("./utils", importing_file, temp_test_dir)
        assert result == str((src / "utils.ts").resolve())

    def test_parent_dir_resolves(self, temp_test_dir):
        (temp_test_dir / "shared.ts").write_text("export {};")
        sub = temp_test_dir / "sub"
        sub.mkdir()
        importing_file = sub / "index.ts"
        importing_file.write_text("")

        result = resolve_ts_import("../shared", importing_file, temp_test_dir)
        assert result == str((temp_test_dir / "shared.ts").resolve())

    def test_directory_with_index(self, temp_test_dir):
        src = temp_test_dir / "src"
        src.mkdir()
        components = src / "components"
        components.mkdir()
        (components / "index.ts").write_text("export {};")
        importing_file = src / "app.ts"
        importing_file.write_text("")

        result = resolve_ts_import("./components", importing_file, temp_test_dir)
        assert result == str((components / "index.ts").resolve())

    def test_tsx_file_resolves(self, temp_test_dir):
        src = temp_test_dir / "src"
        src.mkdir()
        (src / "App.tsx").write_text("export default function App() {}")
        importing_file = src / "index.ts"
        importing_file.write_text("")

        result = resolve_ts_import("./App", importing_file, temp_test_dir)
        assert result == str((src / "App.tsx").resolve())

    def test_deeply_nested_relative(self, temp_test_dir):
        (temp_test_dir / "shared.ts").write_text("export {};")
        deep = temp_test_dir / "a" / "b" / "c"
        deep.mkdir(parents=True)
        importing_file = deep / "index.ts"
        importing_file.write_text("")

        result = resolve_ts_import("../../../shared", importing_file, temp_test_dir)
        assert result == str((temp_test_dir / "shared.ts").resolve())

    def test_nonexistent_relative_returns_none(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        importing_file.write_text("")

        result = resolve_ts_import("./nonexistent", importing_file, temp_test_dir)
        assert result is None


class TestResolveBareSpecifiers:
    def test_react_returns_none(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        result = resolve_ts_import("react", importing_file, temp_test_dir)
        assert result is None

    def test_scoped_package_returns_none(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        result = resolve_ts_import("@kamino-finance/klend-sdk", importing_file, temp_test_dir)
        assert result is None

    def test_node_builtin_returns_none(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        result = resolve_ts_import("path", importing_file, temp_test_dir)
        assert result is None

    def test_subpath_import_returns_none(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        result = resolve_ts_import("lodash/merge", importing_file, temp_test_dir)
        assert result is None

    def test_empty_string_returns_none(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        result = resolve_ts_import("", importing_file, temp_test_dir)
        assert result is None


class TestResolveAliasImports:
    def test_at_alias(self, temp_test_dir):
        src = temp_test_dir / "src"
        utils = src / "utils"
        utils.mkdir(parents=True)
        (utils / "helpers.ts").write_text("export {};")

        importing_file = temp_test_dir / "src" / "app.ts"
        paths_map = {"@/*": ["src/*"]}

        result = resolve_ts_import(
            "@/utils/helpers", importing_file, temp_test_dir,
            base_url=temp_test_dir, paths_map=paths_map,
        )
        assert result == str((utils / "helpers.ts").resolve())

    def test_hash_alias(self, temp_test_dir):
        shared = temp_test_dir / "shared" / "src"
        shared.mkdir(parents=True)
        (shared / "utils.ts").write_text("export {};")

        importing_file = temp_test_dir / "src" / "app.ts"
        paths_map = {"#shared/*": ["shared/src/*"]}

        result = resolve_ts_import(
            "#shared/utils", importing_file, temp_test_dir,
            base_url=temp_test_dir, paths_map=paths_map,
        )
        assert result == str((shared / "utils.ts").resolve())

    def test_exact_alias(self, temp_test_dir):
        src = temp_test_dir / "src"
        src.mkdir()
        (src / "config.ts").write_text("export {};")

        importing_file = temp_test_dir / "src" / "app.ts"
        paths_map = {"$config": ["src/config"]}

        result = resolve_ts_import(
            "$config", importing_file, temp_test_dir,
            base_url=temp_test_dir, paths_map=paths_map,
        )
        assert result == str((src / "config.ts").resolve())

    def test_alias_with_base_url(self, temp_test_dir):
        src = temp_test_dir / "src"
        lib = src / "lib"
        lib.mkdir(parents=True)
        (lib / "math.ts").write_text("export {};")

        importing_file = temp_test_dir / "src" / "app.ts"
        paths_map = {"~/*": ["lib/*"]}

        result = resolve_ts_import(
            "~/math", importing_file, temp_test_dir,
            base_url=src, paths_map=paths_map,
        )
        assert result == str((lib / "math.ts").resolve())

    def test_alias_not_matched_falls_through_to_bare(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        paths_map = {"@/*": ["src/*"]}

        result = resolve_ts_import(
            "react", importing_file, temp_test_dir,
            base_url=temp_test_dir, paths_map=paths_map,
        )
        assert result is None

    def test_alias_file_not_found_returns_none(self, temp_test_dir):
        importing_file = temp_test_dir / "index.ts"
        paths_map = {"@/*": ["src/*"]}

        result = resolve_ts_import(
            "@/nonexistent/module", importing_file, temp_test_dir,
            base_url=temp_test_dir, paths_map=paths_map,
        )
        assert result is None


class TestParseTsconfigPaths:
    def test_basic_with_paths_and_base_url(self, temp_test_dir):
        tsconfig = {
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@/*": ["src/*"],
                    "#shared/*": ["shared/src/*"],
                }
            }
        }
        import json
        (temp_test_dir / "tsconfig.json").write_text(json.dumps(tsconfig))

        base_url, paths_map = parse_tsconfig_paths(temp_test_dir)
        assert base_url == temp_test_dir.resolve()
        assert paths_map == {"@/*": ["src/*"], "#shared/*": ["shared/src/*"]}

    def test_no_tsconfig_returns_defaults(self, temp_test_dir):
        base_url, paths_map = parse_tsconfig_paths(temp_test_dir)
        assert base_url is None
        assert paths_map == {}

    def test_tsconfig_without_paths(self, temp_test_dir):
        tsconfig = {"compilerOptions": {"target": "ES2020"}}
        import json
        (temp_test_dir / "tsconfig.json").write_text(json.dumps(tsconfig))

        base_url, paths_map = parse_tsconfig_paths(temp_test_dir)
        assert base_url is None
        assert paths_map == {}

    def test_tsconfig_with_base_url_subdirectory(self, temp_test_dir):
        src = temp_test_dir / "src"
        src.mkdir()
        tsconfig = {"compilerOptions": {"baseUrl": "./src"}}
        import json
        (temp_test_dir / "tsconfig.json").write_text(json.dumps(tsconfig))

        base_url, paths_map = parse_tsconfig_paths(temp_test_dir)
        assert base_url == src.resolve()
        assert paths_map == {}

    def test_tsconfig_with_comments(self, temp_test_dir):
        content = """{
  // This is a comment
  "compilerOptions": {
    "baseUrl": ".",
    // Another comment
    "paths": {
      "@/*": ["src/*"]
    }
  }
}"""
        (temp_test_dir / "tsconfig.json").write_text(content)

        base_url, paths_map = parse_tsconfig_paths(temp_test_dir)
        assert base_url == temp_test_dir.resolve()
        assert paths_map == {"@/*": ["src/*"]}

    def test_tsconfig_with_trailing_commas(self, temp_test_dir):
        content = """{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
    },
  },
}"""
        (temp_test_dir / "tsconfig.json").write_text(content)

        base_url, paths_map = parse_tsconfig_paths(temp_test_dir)
        assert base_url == temp_test_dir.resolve()
        assert paths_map == {"@/*": ["src/*"]}

    def test_tsconfig_extends(self, temp_test_dir):
        base_tsconfig = {
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {
                    "@base/*": ["base/src/*"]
                }
            }
        }
        child_tsconfig = {
            "extends": "./tsconfig.base.json",
            "compilerOptions": {
                "paths": {
                    "@app/*": ["app/src/*"]
                }
            }
        }
        import json
        (temp_test_dir / "tsconfig.base.json").write_text(json.dumps(base_tsconfig))
        (temp_test_dir / "tsconfig.json").write_text(json.dumps(child_tsconfig))

        base_url, paths_map = parse_tsconfig_paths(temp_test_dir)
        assert base_url == temp_test_dir.resolve()
        assert "@base/*" in paths_map
        assert "@app/*" in paths_map
        assert paths_map["@base/*"] == ["base/src/*"]
        assert paths_map["@app/*"] == ["app/src/*"]


class TestEdgeCases:
    def test_none_paths_map_with_relative_import(self, temp_test_dir):
        (temp_test_dir / "utils.ts").write_text("export {};")
        importing_file = temp_test_dir / "index.ts"
        importing_file.write_text("")

        result = resolve_ts_import("./utils", importing_file, temp_test_dir,
                                   base_url=None, paths_map=None)
        assert result == str((temp_test_dir / "utils.ts").resolve())

    def test_empty_paths_map_with_relative_import(self, temp_test_dir):
        (temp_test_dir / "utils.ts").write_text("export {};")
        importing_file = temp_test_dir / "index.ts"
        importing_file.write_text("")

        result = resolve_ts_import("./utils", importing_file, temp_test_dir,
                                   base_url=None, paths_map={})
        assert result == str((temp_test_dir / "utils.ts").resolve())

    def test_import_with_explicit_extension(self, temp_test_dir):
        (temp_test_dir / "data.json").write_text("{}")
        importing_file = temp_test_dir / "index.ts"

        result = resolve_ts_import("./data.json", importing_file, temp_test_dir)
        assert result == str((temp_test_dir / "data.json").resolve())
