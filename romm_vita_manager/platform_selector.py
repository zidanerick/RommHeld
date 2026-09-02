"""Compatibility exports for the unified handheld selector.

The responsive selector now lives in :mod:`console_selector`. This module is
kept as a compatibility import path for older workspace/dashboard code.
"""

from .console_selector import ConsoleGrid, ConsoleProfile, ConsoleTile, PlatformSelectorDialog

__all__ = [
    "ConsoleGrid",
    "ConsoleProfile",
    "ConsoleTile",
    "PlatformSelectorDialog",
]
