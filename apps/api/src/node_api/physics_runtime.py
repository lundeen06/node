"""Ensure the monorepo ``physics`` package is importable (not installed as a wheel)."""

from __future__ import annotations

import sys

from node_api.repo_root import monorepo_root

_DONE = False


def ensure_physics_importable() -> None:
    global _DONE
    if _DONE:
        return
    root = str(monorepo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    _DONE = True
