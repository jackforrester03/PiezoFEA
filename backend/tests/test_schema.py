import pytest
from pydantic import ValidationError

from app.schema import Project


def test_validation_project_loads(disc_project):
    assert disc_project.port_ids() == ["hot"]


def _modify(project: Project, **changes) -> dict:
    data = project.model_dump()
    data.update(changes)
    return data


def test_unknown_terminal_rejected(disc_project):
    data = disc_project.model_dump()
    data["electrodes"][0]["terminal_id"] = "nope"
    with pytest.raises(ValidationError, match="unknown terminal"):
        Project.model_validate(data)


def test_ground_required(disc_project):
    data = disc_project.model_dump()
    data["terminals"][1]["role"] = "floating"
    with pytest.raises(ValidationError, match="ground"):
        Project.model_validate(data)


def test_extent_must_match_surface(disc_project):
    data = disc_project.model_dump()
    data["electrodes"][0]["surface"] = "outer"
    with pytest.raises(ValidationError, match="band"):
        Project.model_validate(data)
