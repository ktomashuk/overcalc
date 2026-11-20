"""The implementer subagent definition (.claude/agents/implementer.md) is well-formed."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTER = ROOT / ".claude" / "agents" / "implementer.md"


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text()
    assert text.startswith("---\n"), "agent file must start with a --- frontmatter block"
    block, sep, _body = text[4:].partition("\n---\n")
    assert sep, "frontmatter block is not closed"
    data: dict[str, Any] = yaml.safe_load(block)
    return data


def test_implementer_frontmatter() -> None:
    meta = _frontmatter(IMPLEMENTER)
    tools = {t.strip() for t in str(meta["tools"]).split(",")}
    assert meta["name"] == "implementer"
    assert meta["model"] == "opus"
    assert str(meta.get("description", "")).strip()
    assert {"Read", "Edit", "Write", "Bash", "Skill"} <= tools
    assert not any(t.startswith("mcp__") for t in tools), "implementer gets no MCP (Jira) tools"
