"""Analytical reference values for disc validation cases."""

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, j1

from app.materials.convert import EPS0, load_library_material


def disc_radial_fr(material_id: str, radius: float) -> float:
    """Fundamental radial mode of a thin free disc with shorted electrodes."""
    lib = load_library_material(material_id)
    s = lib["s_E"]
    sigma = -s["s12"] / s["s11"]
    eta1 = brentq(lambda x: x * j0(x) - (1 - sigma) * j1(x), 1.5, 2.5)
    return eta1 / (2 * np.pi * radius) * np.sqrt(1 / (lib["density"] * s["s11"] * (1 - sigma**2)))


def disc_free_capacitance(material_id: str, radius: float, thickness: float) -> float:
    lib = load_library_material(material_id)
    return lib["eps_T_rel"]["eps33"] * EPS0 * np.pi * radius**2 / thickness
