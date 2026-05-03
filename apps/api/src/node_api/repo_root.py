"""Repository layout: ``node_api`` lives under ``apps/api/src/node_api``."""

from __future__ import annotations

from pathlib import Path


def monorepo_root() -> Path:
    """Return the monorepo root (directory that contains ``physics/`` and ``apps/``)."""
    # file: apps/api/src/node_api/repo_root.py → parents[4] == repo root
    return Path(__file__).resolve().parents[4]


def api_project_root() -> Path:
    """Return ``apps/api`` (contains ``pyproject.toml`` and default SQLite file)."""
    return Path(__file__).resolve().parents[2]
