#!/usr/bin/env python3
"""Backward-compatible entry point for RomM Vita Manager."""
from __future__ import annotations

from romm_vita_manager.ui import MainWindow, SettingsDialog, SetupWizard, main

__all__ = ["MainWindow", "SettingsDialog", "SetupWizard", "main"]


if __name__ == "__main__":
    main()
