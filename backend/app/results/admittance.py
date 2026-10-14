"""Charge -> current -> admittance."""

import numpy as np
from numpy.typing import NDArray


def current_from_charge(f: NDArray[np.float64], q: NDArray[np.complex128]) -> NDArray[np.complex128]:
    """Phasor current into an electrode, I = j w Q (charge Q on the electrode)."""
    return 1j * 2 * np.pi * f * q
