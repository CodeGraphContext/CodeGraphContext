"""Terminal selection of exact indexed repository keys."""
from collections.abc import Iterable
from typing import Optional

from InquirerPy import inquirer


def select_repository(repositories: Iterable[dict]) -> Optional[str]:
    """Return a stored key without interpreting it as a live filesystem path."""
    # Identical graph keys identify the same repository. Keep display ordering
    # deterministic without changing keys, including legacy Windows paths.
    labels = {}
    for repository in repositories:
        path = repository.get("path")
        if not isinstance(path, str) or not path:
            continue
        name = repository.get("name") or path
        kind = "Dependency" if repository.get("is_dependency") else "Project"
        label = f"{name} — {path} ({kind})"
        labels[path] = min(labels.get(path, label), label)
    choices = [
        {"name": label, "value": path}
        for path, label in sorted(labels.items(), key=lambda item: (item[1].casefold(), item[0]))
    ]
    if not choices:
        return None
    try:
        return inquirer.fuzzy(
            message="Select an indexed repository to delete:",
            choices=choices,
            mandatory=False,
            keybindings={"skip": [{"key": "escape"}, {"key": "c-d"}]},
        ).execute()
    except (KeyboardInterrupt, EOFError):
        return None
