"""Generated XML must validate against the openCFS schemas shipped with the binary."""

from pathlib import Path

import pytest
from lxml import etree

from app.geometry.axisym import AxisymInterpreter
from app.solver.runner import plan_runs
from app.solver.xml_writer import material_xml, simulation_xml

SCHEMA_ROOT = Path("/opt/cfs/share/xml")
pytestmark = pytest.mark.skipif(not SCHEMA_ROOT.exists(), reason="openCFS schemas not installed")


def _validate(xml: bytes, xsd: Path) -> None:
    schema = etree.XMLSchema(etree.parse(str(xsd)))
    doc = etree.fromstring(xml)
    schema.assertValid(doc)


def test_simulation_xml_valid(disc_project):
    m = AxisymInterpreter().interpret(disc_project)
    runs = plan_runs(disc_project, m)
    assert [r.name for r in runs] == ["eigen", "harmonic_hot"]
    for r in runs:
        xml = simulation_xml(m, r.analysis, r.excitation, "../mesh.msh", "../mat.xml")
        _validate(xml, SCHEMA_ROOT / "CFS-Simulation" / "CFS.xsd")
    harm = simulation_xml(m, runs[1].analysis, runs[1].excitation, "../mesh.msh", "../mat.xml").decode()
    assert '<potential name="term_hot" value="1"/>' in harm
    assert '<ground name="term_gnd"/>' in harm
    assert 'complexMaterial="yes"' in harm


def test_open_circuit_eigen_uses_constraint(disc_project):
    data = disc_project.model_dump()
    data["study"]["eigen"]["port_condition"] = "open"
    from app.schema import Project

    p = Project.model_validate(data)
    m = AxisymInterpreter().interpret(p)
    eigen = plan_runs(p, m)[0]
    assert '<constraint name="term_hot"/>' in simulation_xml(m, eigen.analysis, eigen.excitation, "m", "x").decode()


def test_material_xml_valid(disc_project):
    m = AxisymInterpreter().interpret(disc_project)
    for lossless in (True, False):
        _validate(material_xml(m, lossless), SCHEMA_ROOT / "CFS-Material" / "CFS_Material.xsd")
