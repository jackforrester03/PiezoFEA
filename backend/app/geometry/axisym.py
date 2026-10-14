"""2D axisymmetric interpreter: collapses a Project to its r-z cross-section.

Bodies become rectangles [r0, r1] x [z0, z1]; electrodes become straight segments on their
boundaries. Anything the axisymmetric model cannot represent (partial theta ranges, radial
poling) is rejected with an InterpreterError rather than approximated.
"""

import re
from dataclasses import dataclass

from app.geometry.base import InterpreterError
from app.materials.convert import EForm, eform_from_library, library_losses, reverse_poling
from app.schema import AnnulusExtent, BandExtent, DiscBody, Project, RingBody, Terminal

TOL = 1e-9  # m, geometric tolerance


@dataclass(frozen=True)
class AxiMaterial:
    name: str  # name used in the openCFS material file
    eform: EForm
    Qm: float
    tan_delta: float


@dataclass(frozen=True)
class AxiBody:
    id: str
    region: str  # openCFS region / Gmsh physical group name
    r0: float
    r1: float
    z0: float
    z1: float
    material: str  # AxiMaterial.name


@dataclass(frozen=True)
class AxiElectrode:
    id: str
    terminal_id: str
    body_id: str
    p0: tuple[float, float]  # (r, z)
    p1: tuple[float, float]
    neighbor_bodies: tuple[str, ...]  # ids of all bodies whose boundary contains the segment

    @property
    def horizontal(self) -> bool:
        return abs(self.p0[1] - self.p1[1]) < TOL


@dataclass(frozen=True)
class AxiModel:
    bodies: list[AxiBody]
    electrodes: list[AxiElectrode]
    materials: dict[str, AxiMaterial]
    terminals: list[Terminal]
    ports: list[str]

    def body(self, body_id: str) -> AxiBody:
        return next(b for b in self.bodies if b.id == body_id)

    def electrodes_of(self, terminal_id: str) -> list[AxiElectrode]:
        return [e for e in self.electrodes if e.terminal_id == terminal_id]

    def terminal_region(self, terminal_id: str) -> str:
        """openCFS region / Gmsh physical group holding every electrode curve of the terminal."""
        return region_name("term", terminal_id)

    @property
    def terminal_regions(self) -> dict[str, str]:
        return {t.id: self.terminal_region(t.id) for t in self.terminals}

    @property
    def r_max(self) -> float:
        return max(b.r1 for b in self.bodies)


def region_name(prefix: str, ident: str) -> str:
    return f"{prefix}_{re.sub(r'[^A-Za-z0-9_]', '_', ident)}"


def _rect(body: DiscBody | RingBody) -> tuple[float, float, float, float]:
    p = body.params
    if isinstance(body, DiscBody):
        return 0.0, p.radius, p.z_offset, p.z_offset + p.thickness
    return p.inner_radius, p.outer_radius, p.z_offset, p.z_offset + p.thickness


def _segment_on_boundary(b: AxiBody, p0: tuple[float, float], p1: tuple[float, float]) -> bool:
    """True if the segment lies on one edge of the rectangle."""
    (ra, za), (rb, zb) = p0, p1
    if abs(za - zb) < TOL:  # horizontal
        on_edge = abs(za - b.z0) < TOL or abs(za - b.z1) < TOL
        return on_edge and ra >= b.r0 - TOL and rb <= b.r1 + TOL
    on_edge = abs(ra - b.r0) < TOL or abs(ra - b.r1) < TOL
    return on_edge and za >= b.z0 - TOL and zb <= b.z1 + TOL


class AxisymInterpreter:
    def interpret(self, project: Project) -> AxiModel:
        materials: dict[str, AxiMaterial] = {}
        bodies: list[AxiBody] = []
        for body in project.bodies:
            r0, r1, z0, z1 = _rect(body)
            materials_key = self._material(body, materials)
            bodies.append(AxiBody(body.id, region_name("body", body.id), r0, r1, z0, z1, materials_key))
        self._check_overlaps(bodies)

        by_id = {b.id: b for b in bodies}
        electrodes: list[AxiElectrode] = []
        for el in project.electrodes:
            b = by_id[el.body_id]
            ext = el.extent
            if abs((ext.theta_max - ext.theta_min) - 360.0) > 1e-9:
                raise InterpreterError(
                    f"electrode {el.id}: the axisymmetric model needs a full 0-360 deg extent "
                    f"(got {ext.theta_min}-{ext.theta_max} deg); azimuthal segments need the 3D solver"
                )
            p0, p1 = self._segment(el.id, el.surface, ext, b)
            neighbors = tuple(o.id for o in bodies if _segment_on_boundary(o, p0, p1))
            electrodes.append(
                AxiElectrode(el.id, el.terminal_id, el.body_id, p0, p1, neighbors)
            )
        self._check_electrode_overlaps(electrodes)

        regions = [b.region for b in bodies] + [region_name("term", t.id) for t in project.terminals]
        if len(regions) != len(set(regions)):
            raise InterpreterError("body/terminal ids collide after sanitising to region names")
        return AxiModel(bodies, electrodes, materials, project.terminals, project.port_ids())

    @staticmethod
    def _material(body: DiscBody | RingBody, materials: dict[str, AxiMaterial]) -> str:
        direction = body.poling.direction
        if direction not in ("+z", "-z"):
            raise InterpreterError(
                f"body {body.id}: poling '{direction}' is not supported in the axisymmetric model yet "
                "(only +z / -z)"
            )
        name = body.material_id if direction == "+z" else f"{body.material_id}_negz"
        if name not in materials:
            try:
                eform = eform_from_library(body.material_id)
                losses = library_losses(body.material_id)
            except FileNotFoundError:
                raise InterpreterError(f"body {body.id}: unknown material '{body.material_id}'") from None
            if direction == "-z":
                eform = reverse_poling(eform)
            materials[name] = AxiMaterial(name, eform, losses["Qm"], losses["tan_delta"])
        return name

    @staticmethod
    def _check_overlaps(bodies: list[AxiBody]) -> None:
        for i, a in enumerate(bodies):
            for b in bodies[i + 1 :]:
                if min(a.r1, b.r1) - max(a.r0, b.r0) > TOL and min(a.z1, b.z1) - max(a.z0, b.z0) > TOL:
                    raise InterpreterError(f"bodies {a.id} and {b.id} overlap")

    @staticmethod
    def _segment(
        el_id: str, surface: str, ext: AnnulusExtent | BandExtent, b: AxiBody
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        if isinstance(ext, AnnulusExtent):
            if ext.r_min < b.r0 - TOL or ext.r_max > b.r1 + TOL:
                raise InterpreterError(
                    f"electrode {el_id}: r range {ext.r_min}-{ext.r_max} m lies outside the "
                    f"{surface} face ({b.r0}-{b.r1} m)"
                )
            z = b.z1 if surface == "top" else b.z0
            return (ext.r_min, z), (ext.r_max, z)
        if surface == "inner" and b.r0 < TOL:
            raise InterpreterError(f"electrode {el_id}: a disc has no inner surface")
        height = b.z1 - b.z0
        if ext.z_max > height + TOL:
            raise InterpreterError(f"electrode {el_id}: z_max {ext.z_max} m exceeds the body thickness {height} m")
        r = b.r1 if surface == "outer" else b.r0
        return (r, b.z0 + ext.z_min), (r, b.z0 + ext.z_max)

    @staticmethod
    def _check_electrode_overlaps(electrodes: list[AxiElectrode]) -> None:
        for i, a in enumerate(electrodes):
            for b in electrodes[i + 1 :]:
                if a.horizontal != b.horizontal:
                    continue
                k = 0 if a.horizontal else 1  # coordinate along the segment
                line = 1 - k
                if abs(a.p0[line] - b.p0[line]) > TOL:
                    continue
                if min(a.p1[k], b.p1[k]) - max(a.p0[k], b.p0[k]) > TOL:
                    raise InterpreterError(f"electrodes {a.id} and {b.id} overlap")
