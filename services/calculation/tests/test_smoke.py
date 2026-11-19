import pytest

import overcalc_calculation


def test_package_is_importable() -> None:
    assert overcalc_calculation.__name__ == "overcalc_calculation"


@pytest.mark.parametrize("layer", ["domain", "application", "infrastructure", "presentation"])
def test_layers_are_importable(layer: str) -> None:
    __import__(f"overcalc_calculation.{layer}")
