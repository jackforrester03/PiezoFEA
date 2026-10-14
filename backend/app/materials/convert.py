"""Piezo material conversion: datasheet d-form -> e-form used by openCFS.

All tensors use IEEE Voigt ordering (xx, yy, zz, yz, xz, xy) with poling along local 3.
Relations (constant-field compliance s^E, charge constants d, free permittivity eps^T):
    c^E   = (s^E)^-1
    e     = d . c^E
    eps^S = eps^T - d . c^E . d^T
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

EPS0 = 8.8541878128e-12  # F/m

LIBRARY_DIR = Path(__file__).parent / "library"


@dataclass(frozen=True)
class EForm:
    """Material in the e-form (stress-charge form), SI units."""

    density: float
    c_E: NDArray[np.float64]  # 6x6, Pa
    e: NDArray[np.float64]  # 3x6, C/m^2
    eps_S: NDArray[np.float64]  # 3x3, F/m (absolute)


def s_matrix_6mm(s11: float, s12: float, s13: float, s33: float, s44: float) -> NDArray[np.float64]:
    """Compliance for crystal class 6mm (poled ceramic). s66 = 2(s11 - s12)."""
    s66 = 2.0 * (s11 - s12)
    return np.array(
        [
            [s11, s12, s13, 0, 0, 0],
            [s12, s11, s13, 0, 0, 0],
            [s13, s13, s33, 0, 0, 0],
            [0, 0, 0, s44, 0, 0],
            [0, 0, 0, 0, s44, 0],
            [0, 0, 0, 0, 0, s66],
        ],
        dtype=float,
    )


def d_matrix_6mm(d31: float, d33: float, d15: float) -> NDArray[np.float64]:
    """Piezo charge constants for class 6mm, IEEE Voigt columns."""
    return np.array(
        [
            [0, 0, 0, 0, d15, 0],
            [0, 0, 0, d15, 0, 0],
            [d31, d31, d33, 0, 0, 0],
        ],
        dtype=float,
    )


def d_to_e(
    density: float, s_E: NDArray[np.float64], d: NDArray[np.float64], eps_T: NDArray[np.float64]
) -> EForm:
    """Convert d-form to e-form. eps_T is absolute (F/m)."""
    c_E = np.linalg.inv(s_E)
    e = d @ c_E
    eps_S = eps_T - d @ c_E @ d.T
    return EForm(density=density, c_E=c_E, e=e, eps_S=eps_S)


def e_to_d(m: EForm) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Inverse of d_to_e: returns (s_E, d, eps_T absolute)."""
    s_E = np.linalg.inv(m.c_E)
    d = m.e @ s_E
    eps_T = m.eps_S + d @ m.c_E @ d.T
    return s_E, d, eps_T


def load_library_material(material_id: str) -> dict:
    """Read a JSON material file from the library."""
    return json.loads((LIBRARY_DIR / f"{material_id}.json").read_text())


def eform_from_library(material_id: str) -> EForm:
    """Load a 6mm d-form library material and convert it to the e-form."""
    mat = load_library_material(material_id)
    if mat["form"] != "d":
        raise ValueError(f"{material_id}: only d-form library materials are supported")
    s_E = s_matrix_6mm(**mat["s_E"])
    d = d_matrix_6mm(**mat["d"])
    eps_rel = mat["eps_T_rel"]
    eps_T = EPS0 * np.diag([eps_rel["eps11"], eps_rel["eps11"], eps_rel["eps33"]])
    return d_to_e(mat["density"], s_E, d, eps_T)


def reverse_poling(m: EForm) -> EForm:
    """Material poled along -3 instead of +3 (180 deg rotation about local 1).

    Under x -> x, y -> -y, z -> -z every nonzero component of a 6mm e tensor has an odd number
    of y/z indices and flips sign; c^E and eps^S (even rank, 6mm) are unchanged.
    """
    return EForm(density=m.density, c_E=m.c_E.copy(), e=-m.e, eps_S=m.eps_S.copy())


def library_losses(material_id: str) -> dict[str, float]:
    """Loss factors from the library entry: {'Qm': ..., 'tan_delta': ...}."""
    return load_library_material(material_id)["losses"]


def list_library() -> list[dict[str, str]]:
    """Summary of every material in the library: id, name, source."""
    out = []
    for path in sorted(LIBRARY_DIR.glob("*.json")):
        mat = json.loads(path.read_text())
        out.append({"id": mat["id"], "name": mat["name"], "source": mat.get("source", "")})
    return out
