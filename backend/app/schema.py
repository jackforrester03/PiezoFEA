"""Pydantic data model: the single source of truth for a simulation project.

The model is independent of dimension. Electrodes are regions on body surfaces tied to a
terminal; dimension-specific interpreters (geometry/axisym.py, later 3D) decide what they can
represent. SI units throughout.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

PositiveLength = Annotated[float, Field(gt=0)]


class DiscParams(BaseModel):
    radius: PositiveLength
    thickness: PositiveLength
    z_offset: float = 0.0  # z of the bottom face


class RingParams(BaseModel):
    inner_radius: PositiveLength
    outer_radius: PositiveLength
    thickness: PositiveLength
    z_offset: float = 0.0

    @model_validator(mode="after")
    def _radii(self) -> Self:
        if self.inner_radius >= self.outer_radius:
            raise ValueError("ring inner_radius must be smaller than outer_radius")
        return self


class Poling(BaseModel):
    """Poling direction in the global frame. Material constants are given poled along local 3."""

    direction: Literal["+z", "-z", "radial"] | tuple[float, float, float] = "+z"


class DiscBody(BaseModel):
    id: str
    shape: Literal["disc"]
    params: DiscParams
    material_id: str
    poling: Poling = Poling()


class RingBody(BaseModel):
    id: str
    shape: Literal["ring"]
    params: RingParams
    material_id: str
    poling: Poling = Poling()


Body = Annotated[DiscBody | RingBody, Field(discriminator="shape")]


class AnnulusExtent(BaseModel):
    """Region on a flat (top/bottom) face, in absolute radius."""

    kind: Literal["annulus"] = "annulus"
    r_min: float = Field(ge=0)
    r_max: PositiveLength
    theta_min: float = 0.0  # degrees
    theta_max: float = 360.0

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.r_min >= self.r_max:
            raise ValueError("annulus r_min must be smaller than r_max")
        return self


class BandExtent(BaseModel):
    """Region on a cylindrical (outer/inner) face; z measured from the body's bottom face."""

    kind: Literal["band"] = "band"
    z_min: float = Field(ge=0)
    z_max: PositiveLength
    theta_min: float = 0.0
    theta_max: float = 360.0

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.z_min >= self.z_max:
            raise ValueError("band z_min must be smaller than z_max")
        return self


Extent = Annotated[AnnulusExtent | BandExtent, Field(discriminator="kind")]


class Electrode(BaseModel):
    id: str
    body_id: str
    surface: Literal["top", "bottom", "outer", "inner"]
    extent: Extent
    terminal_id: str

    @model_validator(mode="after")
    def _extent_matches_surface(self) -> Self:
        flat = self.surface in ("top", "bottom")
        if flat != (self.extent.kind == "annulus"):
            raise ValueError(
                f"electrode {self.id}: top/bottom surfaces take an 'annulus' extent, "
                "outer/inner surfaces take a 'band' extent"
            )
        return self


class Terminal(BaseModel):
    id: str
    name: str = ""
    role: Literal["port", "ground", "floating"]


class EigenSettings(BaseModel):
    num_modes: int = Field(20, gt=0)
    freq_shift: float = Field(1000.0, ge=0)  # Hz; > 0 avoids the free rigid-body z mode at 0 Hz
    port_condition: Literal["short", "open"] = "short"  # short -> f_r, open -> f_a


class HarmonicSettings(BaseModel):
    f_start: PositiveLength  # Hz
    f_stop: PositiveLength
    n_points: int = Field(gt=0)
    spacing: Literal["lin", "log"] = "lin"

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.f_start > self.f_stop:
            raise ValueError("harmonic f_start must not exceed f_stop")
        return self


class MeshSettings(BaseModel):
    max_element_size: PositiveLength = 0.5e-3
    elements_per_wavelength_at_f_max: float = Field(10.0, gt=0)
    f_max: PositiveLength | None = None  # Hz; defaults to harmonic f_stop
    order: Literal[1, 2] = 2


class Study(BaseModel):
    eigen: EigenSettings | None = None
    harmonic: HarmonicSettings | None = None
    ports: list[str] = []  # terminal ids to excite; empty -> all 'port' terminals
    mesh: MeshSettings = MeshSettings()

    @model_validator(mode="after")
    def _something_to_run(self) -> Self:
        if self.eigen is None and self.harmonic is None:
            raise ValueError("study needs an eigen and/or a harmonic analysis")
        return self


class Project(BaseModel):
    name: str
    units: Literal["SI"] = "SI"
    bodies: list[Body]
    electrodes: list[Electrode]
    terminals: list[Terminal]
    study: Study

    @model_validator(mode="after")
    def _references(self) -> Self:
        for kind, items in (("body", self.bodies), ("electrode", self.electrodes), ("terminal", self.terminals)):
            ids = [i.id for i in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {kind} ids")
        body_ids = {b.id for b in self.bodies}
        terminals = {t.id: t for t in self.terminals}
        for e in self.electrodes:
            if e.body_id not in body_ids:
                raise ValueError(f"electrode {e.id}: unknown body '{e.body_id}'")
            if e.terminal_id not in terminals:
                raise ValueError(f"electrode {e.id}: unknown terminal '{e.terminal_id}'")
        if not any(t.role == "ground" for t in self.terminals):
            raise ValueError("at least one terminal must have role 'ground'")
        for p in self.study.ports:
            if p not in terminals or terminals[p].role != "port":
                raise ValueError(f"study port '{p}' is not a terminal with role 'port'")
        used = {e.terminal_id for e in self.electrodes}
        for t in self.terminals:
            if t.id not in used:
                raise ValueError(f"terminal {t.id} has no electrodes")
        return self

    def port_ids(self) -> list[str]:
        """Ports to excite, in order."""
        return self.study.ports or [t.id for t in self.terminals if t.role == "port"]
