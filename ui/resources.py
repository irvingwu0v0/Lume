"""Locate bundled resources in both source checkouts and PyInstaller builds."""

import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parent.parent


def resource_path(*parts):
    """Return an absolute path to a bundled resource."""
    base = Path(getattr(sys, "_MEIPASS", _SOURCE_ROOT))
    return base.joinpath(*parts)
