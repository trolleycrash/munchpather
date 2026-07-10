"""Shared fixtures. The repo's real data files are the test fixtures."""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def foundry_actor() -> dict:
    (path,) = glob.glob(str(ROOT / "fvtt-Actor-*.json"))
    return json.loads(Path(path).read_text())


@pytest.fixture(scope="session")
def sample_pbex() -> dict:
    (path,) = glob.glob(str(ROOT / "pathbuilderexport*.pbex"))
    return json.loads(Path(path).read_text())


@pytest.fixture(scope="session")
def sample_inner_save(sample_pbex) -> dict:
    """The first character save inside the sample .pbex, decoded."""
    first = next(iter(sample_pbex["saves"].values()))
    return json.loads(first)


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return ROOT / "data"
