"""Terminal charge from the FE solution by the weak form (reaction charge).

openCFS's elecCharge integrates D.n from one side only, and for an electrode between two bodies
it ignores neighborRegion and always uses the same side (verified, CLAUDE.md). Instead we compute

    Q_k = -integral( grad(w_k) . D ) dV,   dV = 2 pi r dr dz,   D = e S + eps E,

where w_k is 1 on the nodes of terminal k and 0 elsewhere (interpolated with the element shape
functions). This is the consistent nodal reaction of the electrostatic equation summed over the
electrode, so it collects flux from every side, and charges over all terminals sum to zero.
Material constants do not depend on frequency, so Q_k = a_k . u + b_k . phi is one linear operator
applied to every step.

Axisymmetric strain in IEEE Voigt order with 1 = r, 2 = theta, 3 = z (the axis):
    S = [du_r/dr, u_r/r, du_z/dz, 0, du_r/dz + du_z/dr, 0],   E = [-dphi/dr, 0, -dphi/dz].
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np
from numpy.typing import NDArray

from app.geometry.axisym import AxiModel

# openCFS element type codes in Mesh/Elements/Types
TRIA3, TRIA6, QUAD4, QUAD8 = 4, 5, 6, 7

ShapeFn = Callable[[float, float], NDArray[np.float64]]


def _tria3(xi: float, eta: float) -> NDArray[np.float64]:
    return np.array([1 - xi - eta, xi, eta])


def _tria6(xi: float, eta: float) -> NDArray[np.float64]:
    l1, l2, l3 = 1 - xi - eta, xi, eta
    return np.array([l1 * (2 * l1 - 1), l2 * (2 * l2 - 1), l3 * (2 * l3 - 1), 4 * l1 * l2, 4 * l2 * l3, 4 * l3 * l1])


_Q_CORNERS = ((-1, -1), (1, -1), (1, 1), (-1, 1))


def _quad4(xi: float, eta: float) -> NDArray[np.float64]:
    return np.array([0.25 * (1 + xi * a) * (1 + eta * b) for a, b in _Q_CORNERS])


def _quad8(xi: float, eta: float) -> NDArray[np.float64]:
    corners = [0.25 * (1 + xi * a) * (1 + eta * b) * (xi * a + eta * b - 1) for a, b in _Q_CORNERS]
    mids = [
        0.5 * (1 - xi**2) * (1 - eta),
        0.5 * (1 + xi) * (1 - eta**2),
        0.5 * (1 - xi**2) * (1 + eta),
        0.5 * (1 - xi) * (1 - eta**2),
    ]
    return np.array(corners + mids)


def _gauss_quad(n: int = 3) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    x, w = np.polynomial.legendre.leggauss(n)
    pts = np.array([(a, b) for a in x for b in x])
    return pts, np.array([wa * wb for wa in w for wb in w])


def _gauss_tria() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """7-point rule, exact to degree 5 (Dunavant), on the reference triangle (area 1/2)."""
    a1, b1 = 0.059715871789770, 0.470142064105115
    a2, b2 = 0.797426985353087, 0.101286507323456
    pts = [(1 / 3, 1 / 3), (b1, b1), (a1, b1), (b1, a1), (b2, b2), (a2, b2), (b2, a2)]
    w = [0.225] + [0.132394152788506] * 3 + [0.125939180544827] * 3
    return np.array(pts), 0.5 * np.array(w)


ELEMENTS: dict[int, tuple[ShapeFn, tuple[NDArray[np.float64], NDArray[np.float64]]]] = {
    TRIA3: (_tria3, _gauss_tria()),
    TRIA6: (_tria6, _gauss_tria()),
    QUAD4: (_quad4, _gauss_quad(2)),
    QUAD8: (_quad8, _gauss_quad(3)),
}


def _shape_and_grad(fn: ShapeFn, xi: float, eta: float) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """N and dN/d(xi, eta). Central differences are exact for these (per-variable quadratic) polynomials."""
    h = 1e-4
    dxi = (fn(xi + h, eta) - fn(xi - h, eta)) / (2 * h)
    deta = (fn(xi, eta + h) - fn(xi, eta - h)) / (2 * h)
    return fn(xi, eta), np.vstack([dxi, deta])


@dataclass(frozen=True)
class ChargeOperator:
    """Q_k = a[k] . u (u: (n_nodes, 2) r/z displacement) + b[k] . phi (phi: (n_nodes,))."""

    terminals: list[str]
    a: NDArray[np.complex128]  # (n_terminals, n_nodes, 2)
    b: NDArray[np.complex128]  # (n_terminals, n_nodes)

    def apply(self, u: NDArray[np.complex128], phi: NDArray[np.complex128]) -> NDArray[np.complex128]:
        return np.einsum("knd,nd->k", self.a, u) + self.b @ phi


def build_operator(f: h5py.File, model: AxiModel, terminal_regions: dict[str, str], lossless: bool) -> ChargeOperator:
    coords = np.asarray(f["Mesh/Nodes/Coordinates"])[:, :2]
    conn = np.asarray(f["Mesh/Elements/Connectivity"])
    types = np.asarray(f["Mesh/Elements/Types"])
    n_nodes = len(coords)
    terminals = list(terminal_regions)
    w = np.zeros((len(terminals), n_nodes))
    for k, region in enumerate(terminal_regions.values()):
        w[k, np.asarray(f[f"Mesh/Regions/{region}/Nodes"]) - 1] = 1.0

    a = np.zeros((len(terminals), n_nodes, 2), dtype=complex)
    b = np.zeros((len(terminals), n_nodes), dtype=complex)
    for body in model.bodies:
        mat = model.materials[body.material]
        e_mat = mat.eform.e
        eps = mat.eform.eps_S * (1 if lossless else (1 - 1j * mat.tan_delta))
        for el in np.asarray(f[f"Mesh/Regions/{body.region}/Elements"]) - 1:
            etype = int(types[el])
            if etype not in ELEMENTS:
                raise NotImplementedError(f"element type {etype} not supported in charge computation")
            fn, (pts, wts) = ELEMENTS[etype]
            nodes = conn[el][conn[el] > 0] - 1
            if not w[:, nodes].any():
                continue  # element does not touch any terminal
            x = coords[nodes]
            for (xi, eta), wt in zip(pts, wts):
                n, dn = _shape_and_grad(fn, xi, eta)
                jac = dn @ x  # [[dr/dxi, dz/dxi], [dr/deta, dz/deta]]
                det = np.linalg.det(jac)
                dndx = np.linalg.solve(jac, dn)  # rows: d/dr, d/dz
                r = n @ x[:, 0]
                # Strain from nodal (u_r, u_z): S[i] = sum_n Bu[i, n, d] u[n, d]
                bu = np.zeros((6, len(nodes), 2))
                bu[0, :, 0] = dndx[0]
                bu[1, :, 0] = n / r
                bu[2, :, 1] = dndx[1]
                bu[4, :, 0] = dndx[1]
                bu[4, :, 1] = dndx[0]
                # E from nodal phi: E = -[dphi/dr, 0, dphi/dz]
                bphi = np.zeros((3, len(nodes)))
                bphi[0] = -dndx[0]
                bphi[2] = -dndx[1]
                d_u = np.einsum("ij,jnd->ind", e_mat, bu)  # D from u
                d_phi = eps @ bphi  # D from phi
                scale = -2 * np.pi * r * det * wt
                for k in range(len(terminals)):
                    gw = dndx @ w[k, nodes]  # grad w_k = (dw/dr, dw/dz)
                    if not gw.any():
                        continue
                    a[k, nodes] += scale * (gw[0] * d_u[0] + gw[1] * d_u[2])
                    b[k, nodes] += scale * (gw[0] * d_phi[0] + gw[1] * d_phi[2])
    return ChargeOperator(terminals, a, b)


def _read_field(step: h5py.Group, name: str, model: AxiModel, region_nodes: dict[str, NDArray], shape: tuple) -> NDArray:
    out = np.zeros(shape, dtype=complex)
    for body in model.bodies:
        g = step[f"{name}/{body.region}/Nodes"]
        vals = np.asarray(g["Real"]) + (1j * np.asarray(g["Imag"]) if "Imag" in g else 0)
        idx = region_nodes[body.region]
        out[idx] = vals if len(shape) == 2 else vals[:, 0]
    return out


def terminal_charges(
    cfs_file: Path, model: AxiModel, terminal_regions: dict[str, str], lossless: bool
) -> tuple[NDArray[np.float64], dict[str, NDArray[np.complex128]]]:
    """Step values (Hz) and the complex charge on each terminal at every step."""
    with h5py.File(cfs_file, "r") as f:
        op = build_operator(f, model, terminal_regions, lossless)
        n_nodes = len(f["Mesh/Nodes/Coordinates"])
        region_nodes = {b.region: np.asarray(f[f"Mesh/Regions/{b.region}/Nodes"]) - 1 for b in model.bodies}
        ms = f["Results/Mesh/MultiStep_1"]
        steps = sorted((k for k in ms if k.startswith("Step_")), key=lambda s: int(s.split("_")[1]))
        freqs = np.array([float(ms[s].attrs["StepValue"][0]) for s in steps])
        q = np.zeros((len(steps), len(op.terminals)), dtype=complex)
        for i, s in enumerate(steps):
            u = _read_field(ms[s], "mechDisplacement", model, region_nodes, (n_nodes, 2))
            phi = _read_field(ms[s], "elecPotential", model, region_nodes, (n_nodes,))
            q[i] = op.apply(u, phi)
    return freqs, {t: q[:, k] for k, t in enumerate(op.terminals)}
