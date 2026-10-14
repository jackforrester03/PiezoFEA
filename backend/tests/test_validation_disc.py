"""End-to-end validation: Project JSON -> mesh -> openCFS -> Y(f), against analytical values.

Runs openCFS (~1-2 min under emulation). Skip with: pytest -m "not slow".
"""

import shutil

import numpy as np
import pytest

from app.solver import runner
from tests.analytical import disc_free_capacitance, disc_radial_fr

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("cfs") is None, reason="openCFS not installed"),
]

A, T = 10.5e-3, 1.5e-3


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    import json
    from pathlib import Path

    from app.schema import Project
    from tests.conftest import VALIDATION

    runner.RUNS_DIR = tmp_path_factory.mktemp("runs")
    project = Project.model_validate(json.loads((Path(VALIDATION) / "disc_pzt4" / "project.json").read_text()))
    status = runner.create_job(project)
    runner.run_job(status.job_id)
    final = runner.read_status(status.job_id)
    assert final.state == "done", final.message
    return runner.read_results(status.job_id).model_dump()


def test_eigen_radial_mode(results):
    eig = results["eigen"]
    f = np.array(eig["frequencies"])
    q = np.array(eig["port_charge"]["hot"])
    active = f[q > 1e-2 * q.max()]
    assert active[0] == pytest.approx(disc_radial_fr("PZT-4", A), rel=0.005)


def _y11(results):
    h = results["harmonic"]
    f = np.array(h["frequencies"])
    y = np.array(h["Y_real"])[:, 0, 0] + 1j * np.array(h["Y_imag"])[:, 0, 0]
    return f, y


def test_harmonic_resonance_and_antiresonance(results):
    f, y = _y11(results)
    step = f[1] - f[0]
    assert f[np.argmax(np.abs(y))] == pytest.approx(disc_radial_fr("PZT-4", A), abs=step + 0.005 * 109e3)
    assert f[np.argmin(np.abs(y))] == pytest.approx(125.9e3, abs=step + 0.005 * 126e3)


def test_low_frequency_capacitance(results):
    f, y = _y11(results)
    c = y[0].imag / (2 * np.pi * f[0])
    assert c == pytest.approx(disc_free_capacitance("PZT-4", A, T), rel=0.02)


def test_passive(results):
    _, y = _y11(results)
    assert np.all(y.real > 0)
