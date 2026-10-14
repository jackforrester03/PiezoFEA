"""openCFS simulation and material XML for the axisymmetric model.

Syntax verified in validation/spike_disc (see CLAUDE.md, openCFS checklist):
- geometryType="axi", mechanic subType="axi", fix dof r on the axis
- ground / potential / constraint (floating equipotential) per terminal region
- electrode charge is NOT taken from openCFS's elecCharge (one-sided on internal electrodes);
  results/charge.py computes it from the stored displacement and potential fields
- complexMaterial="yes" with absolute imaginary parts: c(1 + j/Qm), eps(1 - j tan_delta)
openCFS rejects comments before the root element, so none are written there.
"""

from typing import Literal

import numpy as np
from lxml import etree

from app.geometry.axisym import TOL, AxiModel
from app.mesh.gmsh_axisym import AXIS_REGION
from app.schema import EigenSettings, HarmonicSettings

SIM_NS = "http://www.cfs++.org/simulation"
MAT_NS = "http://www.cfs++.org/material"

Excitation = Literal["ground", "drive", "floating"]


def _sub(parent: etree._Element, tag: str, text: str | None = None, **attrib: str) -> etree._Element:
    el = etree.SubElement(parent, tag, attrib)
    if text is not None:
        el.text = text
    return el


def _matrix(m: np.ndarray) -> str:
    return "\n" + "\n".join(" ".join(f"{v:.9e}" for v in row) for row in m) + "\n"


def _tensor(parent: etree._Element, real: np.ndarray, imag: np.ndarray | None) -> None:
    t = _sub(parent, "tensor", dim1=str(real.shape[0]), dim2=str(real.shape[1]))
    _sub(t, "real", _matrix(real))
    if imag is not None:
        _sub(t, "imag", _matrix(imag))


def material_xml(model: AxiModel, lossless: bool) -> bytes:
    root = etree.Element("cfsMaterialDataBase", nsmap={None: MAT_NS})
    for m in model.materials.values():
        f = m.eform
        mat = _sub(root, "material", name=m.name)
        mech = _sub(mat, "mechanical")
        _sub(_sub(_sub(mech, "density"), "linear"), "real", f"{f.density:.9e}")
        _tensor(_sub(_sub(mech, "elasticity"), "linear"), f.c_E, None if lossless else f.c_E / m.Qm)
        elec = _sub(mat, "electric")
        _tensor(_sub(_sub(elec, "permittivity"), "linear"), f.eps_S, None if lossless else -f.eps_S * m.tan_delta)
        piezo = _sub(mat, "piezo")
        _tensor(_sub(_sub(piezo, "piezoCoupling"), "linear"), f.e, None)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8", pretty_print=True)


def simulation_xml(
    model: AxiModel,
    analysis: EigenSettings | HarmonicSettings,
    excitation: dict[str, Excitation],
    mesh_file: str,
    material_file: str,
) -> bytes:
    """One openCFS run. `excitation` maps every terminal id to ground / drive (1 V) / floating."""
    complex_mat = isinstance(analysis, HarmonicSettings)
    has_axis = any(b.r0 < TOL for b in model.bodies)
    region_attrs = {"complexMaterial": "yes"} if complex_mat else {}

    root = etree.Element("cfsSimulation", nsmap={None: SIM_NS})
    ff = _sub(root, "fileFormats")
    _sub(_sub(ff, "input"), "gmsh", fileName=mesh_file)
    out = _sub(ff, "output")
    _sub(out, "hdf5")
    _sub(out, "text", id="txt")
    _sub(ff, "materialData", file=material_file, format="xml")

    domain = _sub(root, "domain", geometryType="axi")
    regions = _sub(domain, "regionList")
    for b in model.bodies:
        _sub(regions, "region", name=b.region, material=b.material)
    surfs = _sub(domain, "surfRegionList")
    for t in model.terminals:
        _sub(surfs, "surfRegion", name=model.terminal_region(t.id))
    if has_axis:
        _sub(surfs, "surfRegion", name=AXIS_REGION)

    step = _sub(root, "sequenceStep")
    an = _sub(step, "analysis")
    if isinstance(analysis, EigenSettings):
        ev = _sub(an, "eigenFrequency")
        _sub(ev, "isQuadratic", "no")
        _sub(ev, "numModes", str(analysis.num_modes))
        _sub(ev, "freqShift", f"{analysis.freq_shift:g}")
        _sub(ev, "writeModes", "yes")
    else:
        hm = _sub(an, "harmonic")
        _sub(hm, "numFreq", str(analysis.n_points))
        _sub(hm, "startFreq", f"{analysis.f_start:.9g}")
        _sub(hm, "stopFreq", f"{analysis.f_stop:.9g}")
        _sub(hm, "sampling", "linear" if analysis.spacing == "lin" else "log")

    pdes = _sub(step, "pdeList")
    mech = _sub(pdes, "mechanic", subType="axi")
    rl = _sub(mech, "regionList")
    for b in model.bodies:
        _sub(rl, "region", name=b.region, **region_attrs)
    if has_axis:
        _sub(_sub(_sub(mech, "bcsAndLoads"), "fix", name=AXIS_REGION), "comp", dof="r")
    _sub(_sub(_sub(mech, "storeResults"), "nodeResult", type="mechDisplacement"), "allRegions")

    elec = _sub(pdes, "electrostatic")
    rl = _sub(elec, "regionList")
    for b in model.bodies:
        _sub(rl, "region", name=b.region, **region_attrs)
    bcs = _sub(elec, "bcsAndLoads")
    for t in model.terminals:
        region = model.terminal_region(t.id)
        kind = excitation[t.id]
        if kind == "ground":
            _sub(bcs, "ground", name=region)
        elif kind == "drive":
            _sub(bcs, "potential", name=region, value="1")
        else:
            _sub(bcs, "constraint", name=region)
    _sub(_sub(_sub(elec, "storeResults"), "nodeResult", type="elecPotential"), "allRegions")

    piezo = _sub(_sub(_sub(step, "couplingList"), "direct"), "piezoDirect")
    rl = _sub(piezo, "regionList")
    for b in model.bodies:
        _sub(rl, "region", name=b.region, **region_attrs)
    _sub(_sub(_sub(_sub(step, "linearSystems"), "system"), "solverList"), "directLU")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8", pretty_print=True)
