"""Unit tests for the custom `stdlib_only` import-linter contract (tools/importlinter_contracts)."""

from typing import Any

import grimp
import pytest
from importlinter.domain.contract import ContractCheck, InvalidContractOptions
from tools.importlinter_contracts.stdlib_only import StdlibOnlyContract

MODULES = (
    "pkg",
    "pkg.domain",
    "pkg.domain.model",
    "pkg.domain.events",
    "pkg.application",
    # External packages, as grimp records them with include_external_packages=True:
    # squashed to their top-level name.
    "dataclasses",
    "os",
    "__future__",
    "anyio",
)


def _graph(*imports: tuple[str, str]) -> grimp.ImportGraph:
    graph = grimp.ImportGraph()
    for module in MODULES:
        graph.add_module(module)
    for line_number, (importer, imported) in enumerate(imports, start=1):
        graph.add_import(
            importer=importer,
            imported=imported,
            line_number=line_number,
            line_contents=f"import {imported}",
        )
    return graph


def _check(graph: grimp.ImportGraph, **options: Any) -> ContractCheck:
    contract_options: dict[str, Any] = {
        "source_modules": ["pkg.domain"],
        "allowed_modules": ["pkg.domain"],
    }
    contract_options.update(options)
    contract = StdlibOnlyContract(
        name="domain is stdlib only",
        session_options={},
        contract_options=contract_options,
    )
    return contract.check(graph, verbose=False)


def test_stdlib_imports_are_kept() -> None:
    graph = _graph(
        ("pkg.domain.model", "dataclasses"),
        ("pkg.domain.model", "os"),
        ("pkg.domain.events", "__future__"),
    )

    assert _check(graph).kept


def test_imports_of_allowed_internal_modules_are_kept() -> None:
    graph = _graph(("pkg.domain.events", "pkg.domain.model"), ("pkg.domain", "pkg.domain.events"))

    assert _check(graph).kept


def test_third_party_import_breaks_the_contract() -> None:
    graph = _graph(("pkg.domain.model", "dataclasses"), ("pkg.domain.model", "anyio"))

    check = _check(graph)

    assert not check.kept
    assert check.metadata["invalid_imports"] == [
        {
            "importer": "pkg.domain.model",
            "imported": "anyio",
            "line_number": 2,
            "line_contents": "import anyio",
        }
    ]


def test_internal_module_outside_allowed_breaks_the_contract() -> None:
    graph = _graph(("pkg.domain.events", "pkg.application"))

    check = _check(graph)

    assert not check.kept
    assert [i["imported"] for i in check.metadata["invalid_imports"]] == ["pkg.application"]


def test_source_package_itself_is_checked_not_only_its_children() -> None:
    graph = _graph(("pkg.domain", "anyio"))

    assert not _check(graph).kept


def test_allowed_modules_is_optional() -> None:
    graph = _graph(("pkg.domain.model", "os"), ("pkg.domain.events", "pkg.domain.model"))

    check = StdlibOnlyContract(
        name="x", session_options={}, contract_options={"source_modules": ["pkg.domain"]}
    ).check(graph, verbose=False)

    assert not check.kept
    assert [i["imported"] for i in check.metadata["invalid_imports"]] == ["pkg.domain.model"]


def test_missing_source_module_is_an_error_not_a_silent_pass() -> None:
    # A typo in source_modules must not make the contract vacuously kept.
    with pytest.raises(ValueError, match=r"pkg\.domian"):
        _check(_graph(), source_modules=["pkg.domian"])


def test_unknown_option_is_rejected() -> None:
    with pytest.raises(InvalidContractOptions):
        StdlibOnlyContract(
            name="x",
            session_options={},
            contract_options={"source_modules": ["pkg.domain"], "allowed_module": ["pkg"]},
        )
