"""`stdlib_only` contract: source modules may import only the stdlib and explicitly allowed modules.

ARCHITECTURE.md §1.2 says the domain layer is "stdlib only". The built-in `forbidden` contract can
only deny a fixed list of packages, so any third-party package not on that list would slip through.
This contract inverts it into an allowlist: every direct import from a source module must be either
a stdlib module (`sys.stdlib_module_names`, by top-level name) or inside one of `allowed_modules`.

Only direct imports are checked. That's enough: anything a source module may import is either the
stdlib (not in the graph's scope) or an allowed module, and allowed modules are expected to be
source modules themselves (e.g. the domain package allows itself).
"""

import sys
from typing import Any, TypedDict

import grimp
from importlinter import Contract, ContractCheck, fields, output
from importlinter.domain.helpers import module_expressions_to_modules
from importlinter.domain.imports import Module


class InvalidImport(TypedDict):
    importer: str
    imported: str
    line_number: int
    line_contents: str


def _is_stdlib(module_name: str) -> bool:
    return module_name.partition(".")[0] in sys.stdlib_module_names


def _is_within(module_name: str, packages: set[Module]) -> bool:
    module = Module(module_name)
    return any(module == package or module.is_descendant_of(package) for package in packages)


class StdlibOnlyContract(Contract):
    """
    Configuration options:
        - source_modules:  Modules (treated as packages) that may only import the stdlib and
                           `allowed_modules`.
        - allowed_modules: Non-stdlib modules (treated as packages) the source modules may import.
                           (Optional.)
    """

    type_name = "stdlib_only"

    source_modules = fields.ListField(subfield=fields.ModuleExpressionField())
    allowed_modules = fields.ListField(subfield=fields.ModuleExpressionField(), required=False)

    def check(self, graph: grimp.ImportGraph, verbose: bool) -> ContractCheck:
        # raise_if_unmatched: a typo in source_modules must fail loudly, not pass vacuously.
        sources = module_expressions_to_modules(
            graph, self._expressions("source_modules"), as_packages=True, raise_if_unmatched=True
        )
        allowed = module_expressions_to_modules(
            graph, self._expressions("allowed_modules"), as_packages=False
        )

        invalid_imports: list[InvalidImport] = []
        for source in sorted(sources, key=lambda module: module.name):
            output.verbose_print(verbose, f"Checking imports of {source.name}...")
            for imported in sorted(graph.find_modules_directly_imported_by(source.name)):
                if _is_stdlib(imported) or _is_within(imported, allowed):
                    continue
                for detail in graph.get_import_details(importer=source.name, imported=imported):
                    invalid_imports.append(
                        InvalidImport(
                            importer=source.name,
                            imported=imported,
                            line_number=detail["line_number"],
                            line_contents=detail["line_contents"],
                        )
                    )

        return ContractCheck(
            kept=not invalid_imports, metadata={"invalid_imports": invalid_imports}
        )

    def render_broken_contract(self, check: ContractCheck) -> None:
        for invalid in check.metadata["invalid_imports"]:
            output.print_error(
                f"{invalid['importer']} is not allowed to import {invalid['imported']} "
                f"(l.{invalid['line_number']}: {invalid['line_contents']})",
                bold=False,
            )
        output.new_line()
        output.print("Only the stdlib and the contract's allowed_modules may be imported here.")

    def _expressions(self, field_name: str) -> list[Any]:
        # import-linter populates fields dynamically from the config; unset optional ListFields
        # come back as None.
        value: list[Any] | None = getattr(self, field_name)
        return value or []
