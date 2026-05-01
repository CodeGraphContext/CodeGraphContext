from pathlib import Path

from codegraphcontext.core.cgcignore import (
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

    assert merged == ["*.txt", "*.log", "*.png", "*.json"]


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
