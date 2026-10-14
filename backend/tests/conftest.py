import json
from pathlib import Path

import pytest

from app.schema import Project

VALIDATION = Path(__file__).resolve().parents[2] / "validation"
if not VALIDATION.exists():  # inside the container, validation/ is mounted at /validation
    VALIDATION = Path("/validation")


@pytest.fixture
def disc_project() -> Project:
    return Project.model_validate(json.loads((VALIDATION / "disc_pzt4" / "project.json").read_text()))
