"""The contracts in `.importlinter` enforce ARCHITECTURE.md §1, and §6 shows them verbatim.

Each contract is built from the real config and checked against a small synthetic graph shaped
like `overcalc_calculation`, so a config edit that silently loosens a rule fails here.
"""

import configparser
import re
from pathlib import Path
from typing import Any

import grimp
import importlinter.configuration
import pytest
from importlinter import Contract
from importlinter.contracts.forbidden import ForbiddenContract
from tools.importlinter_contracts.stdlib_only import StdlibOnlyContract

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".importlinter"
ARCHITECTURE = ROOT / "ARCHITECTURE.md"

PKG = "overcalc_calculation"
MODULES = (
    PKG,
    f"{PKG}.domain",
    f"{PKG}.domain.model",
    f"{PKG}.application",
    f"{PKG}.application.dto",
    f"{PKG}.application.services",  # a module no contract names explicitly
    f"{PKG}.application.use_cases",
    f"{PKG}.application.interfaces",
    f"{PKG}.application.interfaces.health",
    f"{PKG}.infrastructure",
    f"{PKG}.infrastructure.health",
    "dataclasses",
    "anyio",
)

CONTRACT_CLASSES: dict[str, type[Contract]] = {
    "forbidden": ForbiddenContract,
    "stdlib_only": StdlibOnlyContract,
}


@pytest.fixture(autouse=True, scope="module")
def _configure_importlinter() -> None:
    # Built-in contracts read settings (e.g. the timer) that lint-imports normally configures.
    importlinter.configuration.configure()


def _config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read_string(CONFIG.read_text())
    return parser


def _options(section: configparser.SectionProxy) -> dict[str, Any]:
    # Same multi-line handling as import-linter's IniFileUserOptionReader.
    return {
        key: value.strip().split("\n") if "\n" in value else value for key, value in section.items()
    }


def _contract(contract_id: str) -> Contract:
    config = _config()
    options = _options(config[f"importlinter:contract:{contract_id}"])
    contract_class = CONTRACT_CLASSES[options.pop("type")]
    return contract_class(
        name=options.pop("name"),
        session_options=_options(config["importlinter"]),
        contract_options=options,
    )


def _kept(contract_id: str, importer: str, imported: str) -> bool:
    graph = grimp.ImportGraph()
    for module in MODULES:
        graph.add_module(module)
    graph.add_import(
        importer=importer, imported=imported, line_number=1, line_contents=f"import {imported}"
    )
    return _contract(contract_id).check(graph, verbose=False).kept


def test_stdlib_only_contract_type_is_registered() -> None:
    contract_types = _config()["importlinter"]["contract_types"].strip().split("\n")

    assert (
        "stdlib_only: tools.importlinter_contracts.stdlib_only.StdlibOnlyContract" in contract_types
    )


@pytest.mark.parametrize("imported", ["dataclasses", f"{PKG}.domain.model"])
def test_domain_may_import_stdlib_and_itself(imported: str) -> None:
    assert _kept("calculation-domain-stdlib-only", f"{PKG}.domain", imported)


@pytest.mark.parametrize("imported", ["anyio", f"{PKG}.application"])
def test_domain_may_not_import_anything_else(imported: str) -> None:
    assert not _kept("calculation-domain-stdlib-only", f"{PKG}.domain.model", imported)


@pytest.mark.parametrize(
    "imported",
    [
        f"{PKG}.application",
        f"{PKG}.application.dto",
        f"{PKG}.application.use_cases",
        f"{PKG}.application.services",
    ],
)
def test_infrastructure_may_not_import_application_outside_interfaces(imported: str) -> None:
    assert not _kept("calculation-infra-only-ports", f"{PKG}.infrastructure.health", imported)


@pytest.mark.parametrize("importer", [f"{PKG}.infrastructure", f"{PKG}.infrastructure.health"])
@pytest.mark.parametrize(
    "imported", [f"{PKG}.application.interfaces", f"{PKG}.application.interfaces.health"]
)
def test_infrastructure_may_import_application_interfaces(importer: str, imported: str) -> None:
    assert _kept("calculation-infra-only-ports", importer, imported)


def test_architecture_md_section_6_matches_importlinter() -> None:
    section_6 = ARCHITECTURE.read_text().split("## 6. Enforcement", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"```ini\n(.*?)```", section_6, flags=re.DOTALL)

    assert blocks == [CONFIG.read_text()]
