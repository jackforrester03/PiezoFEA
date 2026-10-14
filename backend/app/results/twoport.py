"""N-port admittance matrix from one harmonic run per driven port.

Run k drives port k with V_k = 1 V and holds all other ports at 0 V, so Y_jk = I_j / V_k = I_j.
"""

import numpy as np
from numpy.typing import NDArray

from app.results.admittance import current_from_charge


def y_matrix(
    ports: list[str],
    runs: dict[str, tuple[NDArray[np.float64], dict[str, NDArray[np.complex128]]]],
) -> tuple[NDArray[np.float64], NDArray[np.complex128]]:
    """runs[k] = (frequencies, {port j: charge on port j}) for the run driving port k at 1 V.

    Returns (f, Y) with Y of shape (n_f, N, N).
    """
    f = runs[ports[0]][0]
    y = np.zeros((len(f), len(ports), len(ports)), dtype=complex)
    for k, driven in enumerate(ports):
        fk, charges = runs[driven]
        if not np.allclose(fk, f, rtol=1e-9):
            raise ValueError(f"run driving {driven} has different frequencies")
        for j, port in enumerate(ports):
            y[:, j, k] = current_from_charge(f, charges[port])
    return f, y


def reciprocity_error(y: NDArray[np.complex128]) -> float:
    """max |Y_jk - Y_kj| / max |Y| over all frequencies; 0 for a single port."""
    if y.shape[1] < 2:
        return 0.0
    return float(np.max(np.abs(y - np.swapaxes(y, 1, 2))) / np.max(np.abs(y)))
