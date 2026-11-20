"""Behavior of the PostToolUse ruff hook (.claude/hooks/ruff_on_edit.py)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "ruff_on_edit.py"


def _run(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _payload(path: Path) -> str:
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(path)}})


def test_formats_edited_python_file(tmp_path: Path) -> None:
    target = tmp_path / "mod.py"
    target.write_text("x=1\n")
    result = _run(_payload(target))
    assert result.returncode == 0, result.stderr
    assert target.read_text() == "x = 1\n"


def test_ignores_non_python_file(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    target.write_text("x=1\n")
    result = _run(_payload(target))
    assert result.returncode == 0
    assert target.read_text() == "x=1\n"


def test_ignores_missing_file(tmp_path: Path) -> None:
    assert _run(_payload(tmp_path / "missing.py")).returncode == 0


def test_ignores_malformed_payload() -> None:
    assert _run("not json").returncode == 0


def test_reports_unfixable_error(tmp_path: Path) -> None:
    target = tmp_path / "bad.py"
    target.write_text("print(undefined_name)\n")
    result = _run(_payload(target))
    assert result.returncode == 2
    assert "F821" in result.stderr
