#!/usr/bin/env python3
"""PostToolUse hook: run ruff format + ruff check --fix on the Python file just edited.

Exit 0: done, or nothing to do (non-.py, missing file, malformed payload).
Exit 2: ruff found problems it can't fix; its output goes to stderr so the agent sees it.
Stdlib only: this runs with the system python3, outside the project venv.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 60


def _edited_file(raw: str) -> Path | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("ruff_on_edit: malformed hook payload, skipping", file=sys.stderr)
        return None
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path:
        return None
    path = Path(file_path)
    if path.suffix != ".py" or not path.is_file():
        return None
    return path.resolve()


def _repo_root(path: Path) -> Path:
    """The edited file's own repo (so worktrees use their own config/venv), else ours."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
            timeout=TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return SCRIPT_ROOT
    top = result.stdout.strip()
    return Path(top) if result.returncode == 0 and top else SCRIPT_ROOT


def _ruff(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--quiet", "--directory", str(root), "ruff", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=TIMEOUT_SECONDS,
    )


def main() -> int:
    path = _edited_file(sys.stdin.read())
    if path is None:
        return 0
    root = _repo_root(path)
    try:
        for args in (("format", str(path)), ("check", "--fix", str(path))):
            result = _ruff(root, *args)
            if result.returncode != 0:
                print(result.stdout + result.stderr, file=sys.stderr)
                return 2
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ruff_on_edit: could not run ruff ({exc}), skipping", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
