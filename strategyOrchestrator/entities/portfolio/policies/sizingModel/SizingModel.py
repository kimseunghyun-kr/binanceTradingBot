def fixed_fraction(frac: float = 0.5):
    """Example: scale every entry by constant fraction (e.g. 0.5)."""
    return lambda *_, **__: frac
