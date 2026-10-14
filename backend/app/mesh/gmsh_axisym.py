"""Gmsh mesh of the r-z cross-section for openCFS (axi): x = r, y = z.

Physical groups: one surface group per body (AxiBody.region), one curve group per terminal
(AxiModel.terminal_region: all curves of all its electrodes), plus 'axis' for curves on r = 0.
Electrode segments are fragmented into the body boundaries, so electrode ends are mesh nodes.
Grouping by terminal keeps every curve in exactly one group (no duplicated line elements) and
lets a floating terminal with several electrodes be a single equipotential constraint.
"""

import threading
from dataclasses import dataclass
from pathlib import Path

import gmsh
import numpy as np

from app.geometry.axisym import TOL, AxiModel
from app.schema import MeshSettings

AXIS_REGION = "axis"

# The Gmsh API keeps global state, so only one mesh is built at a time per process.
_gmsh_lock = threading.Lock()


@dataclass(frozen=True)
class MeshInfo:
    path: Path
    element_size: float  # m, target size away from refinements
    min_wavelength: float | None  # m, slowest bulk (shear) wave at f_max
    num_nodes: int
    num_elements: int


def slowest_wave_speed(model: AxiModel) -> float:
    """Slowest bulk wave speed over all materials: shear, from c^E (conservative)."""
    speeds = []
    for m in model.materials.values():
        c = m.eform.c_E
        speeds.append(np.sqrt(min(c[3, 3], c[5, 5]) / m.eform.density))
    return float(min(speeds))


def target_size(model: AxiModel, settings: MeshSettings, f_max: float | None) -> tuple[float, float | None]:
    h = settings.max_element_size
    wavelength = None
    if f_max:
        wavelength = slowest_wave_speed(model) / f_max
        h = min(h, wavelength / settings.elements_per_wavelength_at_f_max)
    # Always resolve the thinnest body with at least two elements across.
    h = min(h, min(b.z1 - b.z0 for b in model.bodies) / 2)
    return h, wavelength


def build_mesh(model: AxiModel, settings: MeshSettings, f_max: float | None, path: Path) -> MeshInfo:
    h, wavelength = target_size(model, settings, f_max)
    with _gmsh_lock:
        gmsh.initialize(interruptible=False)
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.model.add("axisym")
            occ = gmsh.model.occ

            rects = [occ.addRectangle(b.r0, b.z0, 0, b.r1 - b.r0, b.z1 - b.z0) for b in model.bodies]
            lines = []
            for e in model.electrodes:
                a = occ.addPoint(e.p0[0], e.p0[1], 0)
                b = occ.addPoint(e.p1[0], e.p1[1], 0)
                lines.append(occ.addLine(a, b))
            _, out_map = occ.fragment([(2, t) for t in rects] + [(1, t) for t in lines], [])
            occ.synchronize()

            body_surfs = [[t for d, t in out_map[i] if d == 2] for i in range(len(rects))]
            elec_curves = [[t for d, t in out_map[len(rects) + j] if d == 1] for j in range(len(lines))]
            z_lo = min(b.z0 for b in model.bodies)
            z_hi = max(b.z1 for b in model.bodies)
            eps = 1e-3 * h
            axis_curves = [
                t for _, t in gmsh.model.getEntitiesInBoundingBox(-eps, z_lo - eps, -eps, eps, z_hi + eps, eps, 1)
            ]

            for body, surfs in zip(model.bodies, body_surfs):
                gmsh.model.setPhysicalName(2, gmsh.model.addPhysicalGroup(2, surfs), body.region)
            by_terminal: dict[str, list[int]] = {}
            for el, curves in zip(model.electrodes, elec_curves):
                if not curves:
                    raise RuntimeError(f"electrode {el.id}: no curves after fragmenting")
                by_terminal.setdefault(el.terminal_id, []).extend(curves)
            for terminal_id, curves in by_terminal.items():
                group = gmsh.model.addPhysicalGroup(1, sorted(set(curves)))
                gmsh.model.setPhysicalName(1, group, model.terminal_region(terminal_id))
            if axis_curves:
                gmsh.model.setPhysicalName(1, gmsh.model.addPhysicalGroup(1, axis_curves), AXIS_REGION)

            _size_fields(model, h)
            gmsh.option.setNumber("Mesh.RecombineAll", 1)
            gmsh.option.setNumber("Mesh.Algorithm", 8)  # frontal-Delaunay for quads
            gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 1)  # blossom
            gmsh.option.setNumber("Mesh.ElementOrder", settings.order)
            gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 1)  # 8-node serendipity quads
            gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
            gmsh.option.setNumber("Mesh.SaveAll", 0)  # only physical groups
            gmsh.model.mesh.generate(2)

            node_tags, _, _ = gmsh.model.mesh.getNodes()
            _, elem_tags, _ = gmsh.model.mesh.getElements(2)
            path.parent.mkdir(parents=True, exist_ok=True)
            gmsh.write(str(path))
            return MeshInfo(path, h, wavelength, len(node_tags), sum(len(t) for t in elem_tags))
        finally:
            gmsh.finalize()


def _size_fields(model: AxiModel, h: float) -> None:
    """Uniform size h, refined to h/3 around electrode edges that lie inside a face."""
    gmsh.option.setNumber("Mesh.MeshSizeMax", h)
    corners = {(round(r / TOL), round(z / TOL)) for b in model.bodies for r in (b.r0, b.r1) for z in (b.z0, b.z1)}
    eps = 1e-3 * h
    edge_points: set[int] = set()
    for e in model.electrodes:
        for r, z in (e.p0, e.p1):
            if (round(r / TOL), round(z / TOL)) not in corners and r > TOL:
                # After fragmenting, electrode ends are geometry vertices of the model.
                found = gmsh.model.getEntitiesInBoundingBox(r - eps, z - eps, -eps, r + eps, z + eps, eps, 0)
                edge_points.update(t for _, t in found)
    if not edge_points:
        return
    dist = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(dist, "PointsList", sorted(edge_points))
    thr = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(thr, "InField", dist)
    gmsh.model.mesh.field.setNumber(thr, "SizeMin", h / 3)
    gmsh.model.mesh.field.setNumber(thr, "SizeMax", h)
    gmsh.model.mesh.field.setNumber(thr, "DistMin", h / 2)
    gmsh.model.mesh.field.setNumber(thr, "DistMax", 3 * h)
    gmsh.model.mesh.field.setAsBackgroundMesh(thr)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
