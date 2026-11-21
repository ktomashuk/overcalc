"""Guardrails for the committed Claude Code settings (.claude/settings.json)."""

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SHARED_SETTINGS = ROOT / ".claude" / "settings.json"

REQUIRED_DENY = {
    "Bash(gh pr merge:*)",
    "Bash(git push --force:*)",
    "Bash(git push -f:*)",
    "Bash(git push --force-with-lease:*)",
    "Bash(git push origin main:*)",
    "Bash(git push origin HEAD:main:*)",
    "Bash(git push -u origin main:*)",
    # Mid-pattern wildcards: the `git push -u origin OVC-:*` allow rule would otherwise
    # auto-approve dangerous suffixes (`OVC-2-x --force`, `+OVC-2-x`, `OVC-2-x:main`).
    "Bash(git push * --force*)",
    "Bash(git push * -f*)",
    "Bash(git push * +*)",
    "Bash(git push *:main*)",
    "Bash(git push * main*)",
    "Bash(git push * --mirror*)",
    "Bash(git push * --delete*)",
    "Bash(git reset --hard:*)",
    "Bash(git clean:*)",
    "Bash(rm -rf:*)",
    "Read(**/.claude/settings.local.json)",
    "Edit(**/.claude/settings.local.json)",
    "Edit(**/.claude/settings.json)",
}


def _check_ignore(path: str) -> int:
    # --no-index: judge the path by the ignore rules alone. Without it, git skips tracked
    # files, so "settings.json is not ignored" would pass even after a bad .gitignore edit.
    return subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", path], cwd=ROOT, check=False
    ).returncode


def _settings() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SHARED_SETTINGS.read_text())
    return data


def test_local_settings_are_gitignored() -> None:
    assert _check_ignore(".claude/settings.local.json") == 0


def test_local_settings_in_subdirectories_are_gitignored() -> None:
    # A session started from a subdirectory writes its own .claude/settings.local.json there.
    assert _check_ignore("services/calculation/.claude/settings.local.json") == 0


def test_shared_settings_are_not_ignored() -> None:
    assert _check_ignore(".claude/settings.json") == 1


def test_required_deny_rules_present() -> None:
    missing = REQUIRED_DENY - set(_settings()["permissions"]["deny"])
    assert not missing, f"missing deny rules: {sorted(missing)}"


def test_no_secrets_in_shared_settings() -> None:
    text = SHARED_SETTINGS.read_text()
    for marker in ("ghp_", "github_pat_", "GH_TOKEN"):
        assert marker not in text
