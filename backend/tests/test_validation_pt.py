"""Two-port and internal-electrode validation (see validation/ringdot_pt/README.md)."""

import json
import shutil

import numpy as np
import pytest

from app.schema import Project
from app.solver import runner
from tests.conftest import VALIDATION

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("cfs") is None, reason="openCFS not installed"),
]


def _load(case: str) -> dict:
    return json.loads((VALIDATION / case / "project.json").read_text())


def _run(data: dict, tmp_path_factory) -> dict:
    runner.RUNS_DIR = tmp_path_factory.mktemp("runs")
    status = runner.create_job(Project.model_validate(data))
    runner.run_job(status.job_id)
    final = runner.read_status(status.job_id)
    assert final.state == "done", final.message
    return runner.read_results(status.job_id).model_dump()


def _y(results: dict) -> tuple[np.ndarray, np.ndarray]:
    h = results["harmonic"]
    return np.array(h["frequencies"]), np.array(h["Y_real"]) + 1j * np.array(h["Y_imag"])


@pytest.fixture(scope="module")
def ringdot(tmp_path_factory):
    return _run(_load("ringdot_pt"), tmp_path_factory)


@pytest.fixture(scope="module")
def ringdot_tied(tmp_path_factory):
    data = _load("ringdot_pt")
    data["electrodes"][1]["terminal_id"] = "in"  # ring onto the dot's terminal
    data["terminals"] = [t for t in data["terminals"] if t["id"] != "out"]
    data["study"]["eigen"]["port_condition"] = "open"
    return _run(data, tmp_path_factory)


def test_reciprocal_and_passive(ringdot):
    f, y = _y(ringdot)
    assert y.shape == (len(f), 2, 2)
    assert ringdot["harmonic"]["reciprocity_error"] < 1e-6
    assert ringdot["harmonic"]["charge_balance_error"] < 1e-9
    for m in y:
        g = (m + m.conj().T) / 2  # Hermitian part; >= 0 for a passive network
        assert np.linalg.eigvalsh(g).min() > -1e-12 * np.abs(m).max()


def test_tied_ports_equal_sum_of_y(ringdot, ringdot_tied):
    f, y = _y(ringdot)
    ft, yt = _y(ringdot_tied)
    assert np.allclose(f, ft)
    expected = y.sum(axis=(1, 2))
    assert np.max(np.abs(yt[:, 0, 0] - expected) / np.abs(expected)) < 1e-6


def test_floating_multi_electrode_terminal(ringdot_tied):
    """Open-circuit eigen (one constraint over dot + ring) finds the antiresonance of the tied port."""
    f, y = _y(ringdot_tied)
    step = f[1] - f[0]
    fa_sweep = f[np.argmin(np.abs(y[:, 0, 0]))]
    eig = np.array(ringdot_tied["eigen"]["frequencies"])
    assert np.min(np.abs(eig - fa_sweep)) <= step


@pytest.fixture(scope="module")
def bimorph(tmp_path_factory):
    return _run(_load("bimorph"), tmp_path_factory)


@pytest.fixture(scope="module")
def single(tmp_path_factory):
    return _run(_load("disc_pzt4"), tmp_path_factory)


def test_bimorph_is_four_times_single_disc(bimorph, single):
    f, yb = _y(bimorph)
    fs, ys = _y(single)
    assert np.allclose(f, fs)
    yb, ys = yb[:, 0, 0], ys[:, 0, 0]
    # Capacitance (20 kHz) and the radial resonance must match 4x / same frequency.
    assert yb[0] / ys[0] == pytest.approx(4.0, rel=2e-3)
    assert f[np.argmax(np.abs(yb))] == f[np.argmax(np.abs(ys))]
    assert np.abs(yb).max() / np.abs(ys).max() == pytest.approx(4.0, rel=0.02)
    eb = np.array(bimorph["eigen"]["frequencies"])
    qb = np.array(bimorph["eigen"]["port_charge"]["hot"])
    es = np.array(single["eigen"]["frequencies"])
    qs = np.array(single["eigen"]["port_charge"]["hot"])
    assert eb[qb > 1e-2 * qb.max()][0] == pytest.approx(es[qs > 1e-2 * qs.max()][0], rel=1e-3)
