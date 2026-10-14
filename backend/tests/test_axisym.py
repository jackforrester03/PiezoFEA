import re

import pytest

from app.geometry.axisym import AxisymInterpreter
from app.geometry.base import InterpreterError
from app.mesh.gmsh_axisym import build_mesh
from app.schema import Project


def test_disc_interpretation(disc_project):
    m = AxisymInterpreter().interpret(disc_project)
    (b,) = m.bodies
    assert (b.r0, b.r1, b.z0, b.z1) == (0.0, 0.0105, 0.0, 0.0015)
    top = next(e for e in m.electrodes if e.id == "top")
    assert top.p0 == (0.0, 0.0015) and top.p1 == (0.0105, 0.0015)
    assert top.neighbor_bodies == ("disc",)
    assert m.ports == ["hot"]


def test_partial_theta_rejected(disc_project):
    data = disc_project.model_dump()
    data["electrodes"][0]["extent"]["theta_max"] = 180.0
    with pytest.raises(InterpreterError, match="0-360"):
        AxisymInterpreter().interpret(Project.model_validate(data))


def test_negative_poling_flips_e(disc_project):
    data = disc_project.model_dump()
    data["bodies"][0]["poling"]["direction"] = "-z"
    m = AxisymInterpreter().interpret(Project.model_validate(data))
    (mat,) = m.materials.values()
    assert mat.name == "PZT-4_negz"
    assert mat.eform.e[2, 2] < 0


def test_two_layer_stack_and_band_electrode(disc_project):
    data = disc_project.model_dump()
    upper = dict(data["bodies"][0], id="upper")
    upper["params"] = dict(upper["params"], z_offset=0.0015)
    data["bodies"].append(upper)
    data["electrodes"][0]["body_id"] = "upper"
    data["electrodes"].append(
        {"id": "ring_band", "body_id": "upper", "surface": "outer",
         "extent": {"kind": "band", "z_min": 0.0, "z_max": 0.0005}, "terminal_id": "gnd"}
    )
    m = AxisymInterpreter().interpret(Project.model_validate(data))
    band = next(e for e in m.electrodes if e.id == "ring_band")
    assert band.p0 == (0.0105, 0.0015) and band.p1 == (0.0105, 0.002)


def test_overlapping_bodies_rejected(disc_project):
    data = disc_project.model_dump()
    data["bodies"].append(dict(data["bodies"][0], id="other"))
    with pytest.raises(InterpreterError, match="overlap"):
        AxisymInterpreter().interpret(Project.model_validate(data))


def test_mesh_physical_groups(disc_project, tmp_path):
    data = disc_project.model_dump()
    # Partial top electrode: the top edge must be split at r = 6 mm.
    data["electrodes"][0]["extent"]["r_max"] = 0.006
    m = AxisymInterpreter().interpret(Project.model_validate(data))
    info = build_mesh(m, disc_project.study.mesh, 200e3, tmp_path / "mesh.msh")
    text = info.path.read_text()
    assert text.startswith("$MeshFormat\n2.2")
    names = set(re.findall(r'^\d+ \d+ "(.+)"$', text, re.M))
    assert names == {"body_disc", "term_hot", "term_gnd", "axis"}
    assert info.element_size == pytest.approx(0.25e-3)
    # Every node of the top electrode lies within r <= 6 mm on z = t.
    nodes_section = text.split("$Nodes\n")[1].split("$EndNodes")[0].splitlines()[1:]
    coords = {int(l.split()[0]): tuple(map(float, l.split()[1:3])) for l in nodes_section}
    phys = {name: int(tag) for tag, name in re.findall(r'^\d+ (\d+) "(.+)"$', text, re.M)}
    elems = text.split("$Elements\n")[1].split("$EndElements")[0].splitlines()[1:]
    top_nodes = set()
    for line in elems:
        parts = list(map(int, line.split()))
        ntags = parts[2]
        if parts[3] == phys["term_hot"]:
            top_nodes.update(parts[3 + ntags :])
    assert top_nodes
    assert all(coords[n][0] <= 0.006 + 1e-12 and coords[n][1] == pytest.approx(0.0015) for n in top_nodes)
