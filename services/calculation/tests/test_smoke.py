def test_package_is_importable() -> None:
    import overcalc_calculation

    assert overcalc_calculation.__name__ == "overcalc_calculation"
