#!/usr/bin/env python3
"""Resolve fonts from the reproducible environment or common Linux paths."""

from __future__ import annotations

import os
from pathlib import Path


def dejavu_sans() -> Path:
    candidates = (
        os.environ.get("DEJAVU_FONT_PATH"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        if candidate and (path := Path(candidate)).is_file():
            return path
    raise FileNotFoundError(
        "DejaVuSans.ttf not found; enter `nix develop` or set DEJAVU_FONT_PATH"
    )
