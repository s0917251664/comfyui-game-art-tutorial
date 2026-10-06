"""Skip a whole test module cleanly when optional third-party deps are missing or broken."""
import importlib
import unittest


def require(*modules):
    missing = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception:  # missing, or installed but failing to load (e.g. broken native libs)
            missing.append(name)
    if missing:
        raise unittest.SkipTest("missing optional dependencies: " + ", ".join(missing))
