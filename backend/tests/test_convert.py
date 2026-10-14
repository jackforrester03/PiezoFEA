"""d-form -> e-form conversion checked against published PZT-4 e-form constants.

Reference (Berlincourt et al., Morgan Electro Ceramics TP-226, PZT-4):
c11E=13.9e10, c12E=7.78e10, c13E=7.43e10, c33E=11.5e10, c44E=2.56e10 Pa,
e31=-5.2, e33=15.1, e15=12.7 C/m^2, eps11S/eps0=730, eps33S/eps0=635.
"""

import numpy as np
import pytest

from app.materials.convert import EPS0, e_to_d, eform_from_library


@pytest.fixture
def pzt4():
    return eform_from_library("PZT-4")


def test_pzt4_stiffness(pzt4):
    c = pzt4.c_E
    assert c[0, 0] == pytest.approx(13.9e10, rel=0.01)
    assert c[0, 1] == pytest.approx(7.78e10, rel=0.01)
    assert c[0, 2] == pytest.approx(7.43e10, rel=0.01)
    assert c[2, 2] == pytest.approx(11.5e10, rel=0.01)
    assert c[3, 3] == pytest.approx(2.56e10, rel=0.01)


def test_pzt4_e_constants(pzt4):
    e = pzt4.e
    assert e[2, 0] == pytest.approx(-5.2, rel=0.02)
    assert e[2, 2] == pytest.approx(15.1, rel=0.01)
    assert e[0, 4] == pytest.approx(12.7, rel=0.01)
    assert e[1, 3] == pytest.approx(12.7, rel=0.01)


def test_pzt4_clamped_permittivity(pzt4):
    # The published d-form and e-form tables are rounded independently and are not mutually
    # consistent for eps^S: from the d-form, eps11S = 1475 - 713 = 762 eps0 (table: 730) and
    # eps33S = 1300 - 637 = 663 eps0 (table: 635). Both within ~5%; c^E and e agree to 1-2%.
    assert pzt4.eps_S[0, 0] / EPS0 == pytest.approx(730, rel=0.05)
    assert pzt4.eps_S[2, 2] / EPS0 == pytest.approx(635, rel=0.05)


def test_round_trip(pzt4):
    s_E, d, eps_T = e_to_d(pzt4)
    assert d[2, 2] == pytest.approx(289e-12, rel=1e-9)
    assert d[2, 0] == pytest.approx(-123e-12, rel=1e-9)
    assert eps_T[2, 2] / EPS0 == pytest.approx(1300, rel=1e-9)
    assert np.allclose(np.linalg.inv(s_E), pzt4.c_E, rtol=1e-9)


def test_reverse_poling_flips_only_e(pzt4):
    from app.materials.convert import reverse_poling

    r = reverse_poling(pzt4)
    assert np.allclose(r.e, -pzt4.e)
    assert np.allclose(r.c_E, pzt4.c_E)
    assert np.allclose(r.eps_S, pzt4.eps_S)
    # Explicit tensor rotation R = diag(1, -1, -1) applied to e_ijk gives the same result.
    voigt = {(0, 0): 0, (1, 1): 1, (2, 2): 2, (1, 2): 3, (2, 1): 3, (0, 2): 4, (2, 0): 4, (0, 1): 5, (1, 0): 5}
    R = np.diag([1.0, -1.0, -1.0])
    e3 = np.zeros((3, 3, 3))
    for i in range(3):
        for (j, k), v in voigt.items():
            e3[i, j, k] = pzt4.e[i, v]
    e3r = np.einsum("ia,jb,kc,abc->ijk", R, R, R, e3)
    for i in range(3):
        for (j, k), v in voigt.items():
            assert e3r[i, j, k] == pytest.approx(r.e[i, v], abs=1e-12)
