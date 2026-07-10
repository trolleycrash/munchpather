"""Shared fixtures.

The fixtures are synthetic (no real character data): ``sample_actor.json`` is a
fabricated Foundry PF2e actor and ``sample.pbex`` encodes only the Pathbuilder
save schema. Both live in tests/fixtures/.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def foundry_actor() -> dict:
    return json.loads((FIXTURES / "sample_actor.json").read_text())


@pytest.fixture(scope="session")
def sample_pbex() -> dict:
    return json.loads((FIXTURES / "sample.pbex").read_text())


@pytest.fixture(scope="session")
def sample_inner_save(sample_pbex) -> dict:
    """The first character save inside the sample .pbex, decoded."""
    first = next(iter(sample_pbex["saves"].values()))
    return json.loads(first)


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return ROOT / "data"
