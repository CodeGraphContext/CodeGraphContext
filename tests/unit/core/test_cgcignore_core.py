from pathlib import Path

import pytest

from codegraphcontext.core.cgcignore import (
    CGCIgnoreMatcher,
    build_ignore_spec,
    parse_cgcignore_lines,
    read_cgcignore_patterns,
)


def test_parse_cgcignore_lines_skips_comments_and_blanks():
    lines = [
        "",
        "   ",
        "# comment",
        "  # spaced comment",
        "*.txt",
        " *.json ",
    ]

    assert parse_cgcignore_lines(lines) == ["*.txt", "*.json"]


def test_build_ignore_spec_merges_default_and_user_patterns(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    cgcignore = repo / ".cgcignore"
    cgcignore.write_text("# only ignore text\n*.txt\n\n*.log\n", encoding="utf-8")

    default_patterns = ["*.png", "*.mp4"]
    spec, resolved = build_ignore_spec(ignore_root=repo, default_patterns=default_patterns)

    assert resolved == cgcignore
    assert spec.match_file("assets/icon.png")
    assert spec.match_file("logs/debug.log")
    assert spec.match_file("notes.txt")
    assert not spec.match_file("src/main.py")
    assert not spec.match_file("config.json")


def test_build_ignore_spec_auto_creates_cgcignore_with_defaults(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    default_patterns = ["*.png", "*.zip"]
    spec, resolved = build_ignore_spec(ignore_root=repo, default_patterns=default_patterns)

    assert resolved == repo / ".cgcignore"
    assert resolved.exists()

    content = resolved.read_text(encoding="utf-8")
    assert "*.png" in content
    assert "*.zip" in content

    assert spec.match_file("image.png")
    assert spec.match_file("archives/data.zip")
    assert not spec.match_file("src/main.py")


def test_read_cgcignore_patterns_merges_defaults_with_user_patterns(tmp_path: Path):
    cgcignore = tmp_path / ".cgcignore"
    cgcignore.write_text("# comment\n\n*.txt\n*.log\n", encoding="utf-8")

    merged = read_cgcignore_patterns(cgcignore, ["*.png", "*.json"])

    # Defaults come first and user patterns last: matching is last-match-wins,
    # so the trailing entries are the ones that win.
    assert merged == ["*.png", "*.json", "*.txt", "*.log"]


def test_user_negation_overrides_default_pattern(tmp_path: Path):
    """A `!pattern` in .cgcignore must be able to re-include a default-ignored path."""
    cgcignore = tmp_path / ".cgcignore"
    cgcignore.write_text("!build/\n!*.svg\n", encoding="utf-8")

    spec, _ = build_ignore_spec(tmp_path, ["build/", "dist/", "*.svg"])

    assert not spec.match_file("build/foo.py")
    assert not spec.match_file("assets/logo.svg")
    # Defaults the user did not negate still apply.
    assert spec.match_file("dist/bundle.js")


@pytest.mark.parametrize(
    "pattern,path,ignored",
    [
        # `**` spans whole segments, so it must not match inside one.
        ("docs/**", "docstring.py", False),
        ("docs/**", "docs_helper/x.py", False),
        ("**/build", "rebuild/x.py", False),
        ("**/build", "xbuild", False),
        ("vendor/**/*.go", "vendorabc.go", False),
        ("src/**/test", "src_foo_test", False),
        # ...but it must still match across whole segments.
        ("docs/**", "docs/a.py", True),
        ("docs/**", "docs/deep/nested/a.py", True),
        ("**/build", "build", True),
        ("**/build", "a/b/build", True),
        ("vendor/**/*.go", "vendor/x.go", True),
        ("vendor/**/*.go", "vendor/a/b.go", True),
        ("src/**/test", "src/test", True),
        ("src/**/test", "src/a/test", True),
    ],
)
def test_double_star_respects_path_segment_boundaries(pattern, path, ignored):
    assert CGCIgnoreMatcher([pattern], Path("/repo")).match_file(path) is ignored


def test_find_cgcignore_does_not_escape_non_git_root(tmp_path: Path):
    parent = tmp_path / "parent"
    repo = parent / "repo"
    parent.mkdir()
    repo.mkdir()

    # A parent-level .cgcignore should not be applied when indexing a path
    # outside a git worktree.
    (parent / ".cgcignore").write_text("*.txt\n", encoding="utf-8")

    default_patterns = ["*.png"]
    spec, resolved = build_ignore_spec(ignore_root=repo, default_patterns=default_patterns)

    assert resolved == repo / ".cgcignore"
    assert (repo / ".cgcignore").exists()
    assert spec.match_file("image.png")
    assert not spec.match_file("notes.txt")


def test_build_ignore_spec_prefers_local_over_explicit_context_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    local_cgcignore = repo / ".cgcignore"
    local_cgcignore.write_text("*.txt\n", encoding="utf-8")

    context_cgcignore = tmp_path / "context" / ".cgcignore"
    context_cgcignore.parent.mkdir(parents=True)
    context_cgcignore.write_text("*.json\n", encoding="utf-8")

    spec, resolved = build_ignore_spec(
        ignore_root=repo,
        default_patterns=["*.png"],
        explicit_path=str(context_cgcignore),
    )

    assert resolved == local_cgcignore
    assert spec.match_file("notes.txt")
    assert spec.match_file("config.json")
    assert spec.match_file("assets/image.png")
    assert not spec.match_file("src/main.py")


def test_build_ignore_spec_auto_creates_local_even_with_explicit_context_file(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    context_cgcignore = tmp_path / "context" / ".cgcignore"
    context_cgcignore.parent.mkdir(parents=True)
    context_cgcignore.write_text("*.txt\n", encoding="utf-8")

    spec, resolved = build_ignore_spec(
        ignore_root=repo,
        default_patterns=["*.png"],
        explicit_path=str(context_cgcignore),
    )

    assert resolved == repo / ".cgcignore"
    assert resolved.exists()
    assert spec.match_file("notes.txt")
    assert spec.match_file("assets/image.png")
    assert not spec.match_file("src/main.py")


def test_safe_walk_directory_pruning_and_error_handling(tmp_path: Path, monkeypatch):
    from codegraphcontext.tools.indexing.discovery import safe_walk
    from pathspec import PathSpec
    from pathspec.patterns import GitWildMatchPattern

    repo = tmp_path / "repo"
    repo.mkdir()

    # Create directory structure
    (repo / "src").mkdir()
    (repo / "src" / "main.py").touch()
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "package.json").touch()
    (repo / "restricted_dir").mkdir()
    (repo / "restricted_dir" / "secret.txt").touch()

    # 1. Test pruning with .cgcignore patterns
    spec = PathSpec.from_lines(GitWildMatchPattern, ["node_modules/"])
    files = safe_walk(repo, spec=spec, ignore_root=repo)
    file_names = {f.name for f in files}
    assert "main.py" in file_names
    assert "package.json" not in file_names
    assert "secret.txt" in file_names

    # 2. Test pruning with IGNORE_DIRS
    files_pruned_dirs = safe_walk(repo, ignore_dirs={"restricted_dir"}, ignore_root=repo)
    pruned_names = {f.name for f in files_pruned_dirs}
    assert "main.py" in pruned_names
    assert "package.json" in pruned_names
    assert "secret.txt" not in pruned_names

    # 3. Test walk error handling / OSError recovery
    import os
    original_walk = os.walk

    def mock_walk(top, topdown=True, onerror=None, followlinks=False):
        if onerror and "restricted_dir" in top:
            onerror(PermissionError("Permission Denied mock error"))
            return iter([])
        return original_walk(top, topdown=topdown, onerror=onerror, followlinks=followlinks)

    monkeypatch.setattr(os, "walk", mock_walk)

    # Walk should run successfully without raising PermissionError and still find other files
    files_with_error = safe_walk(repo, ignore_root=repo)
    recovered_names = {f.name for f in files_with_error}
    assert "main.py" in recovered_names


def test_directory_pattern_requires_segment_boundary():
    """Regression: a directory pattern like ``out/`` must match the path
    *segment* ``out`` only, not the substring inside ``layout/`` /
    ``checkout/`` etc. ``match_file`` applies the compiled regex via
    ``re.search``, so the anchor must require a segment boundary.
    """
    matcher = CGCIgnoreMatcher(["out/", "build/", "target/"], Path("/repo"))

    # Genuine directory matches still work.
    assert matcher.match_file("out/")
    assert matcher.match_file("apps/out/x/")
    assert matcher.match_file("dist/build/")

    # Substring false-positives must NOT be ignored.
    assert not matcher.match_file("layout/")
    assert not matcher.match_file("checkout/")
    assert not matcher.match_file("apps/web/src/components/layout/Header.tsx")
    assert not matcher.match_file("rebuild/")
    assert not matcher.match_file("retarget/")


def test_default_patterns_cover_dotnet_obj_dir():
    """#1585: .NET's obj/ holds *generated source* (AssemblyInfo.cs,
    GlobalUsings.g.cs); indexing it added phantom File/Module/IMPORTS rows
    that silently drifted the C# golden."""
    from codegraphcontext.tools.indexing.constants import DEFAULT_IGNORE_PATTERNS
    from codegraphcontext.cli.config_manager import DEFAULT_CGCIGNORE_PATTERNS
    assert "obj/" in DEFAULT_IGNORE_PATTERNS
    assert "obj/" in DEFAULT_CGCIGNORE_PATTERNS.splitlines()
