"""Spike: compare openCFS results for the PZT-4 disc with analytical estimates.

Reads the per-case .hist text files (elecCharge on 'top') from /data/runs/spike_disc and writes
admittance CSVs plus a standalone Plotly HTML page to /data/runs/spike_disc/.
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, j1

sys.path.insert(0, "/app")
from app.materials.convert import EPS0, eform_from_library, load_library_material  # noqa: E402

RADIUS = 15e-3
THICKNESS = 2.1e-3
RUNS = Path("/data/runs/spike_disc")


def read_hist(case: str, region: str = "top") -> np.ndarray:
    """Columns: f, amplitude, phase(deg)."""
    path = RUNS / case / "history" / f"{case}-elecCharge-surfRegion-{region}.hist"
    return np.loadtxt(path, comments="#")


def analytical() -> dict[str, float]:
    lib = load_library_material("PZT-4")
    s = lib["s_E"]
    rho = lib["density"]
    sigma = -s["s12"] / s["s11"]
    # Fundamental radial (planar) mode of a thin free disc, shorted electrodes:
    # eta J0(eta) = (1 - sigma) J1(eta)
    eta1 = brentq(lambda x: x * j0(x) - (1 - sigma) * j1(x), 1.5, 2.5)
    f_radial = eta1 / (2 * np.pi * RADIUS) * np.sqrt(1 / (rho * s["s11"] * (1 - sigma**2)))
    # Thickness-extensional antiresonance of a laterally clamped plate: f_a = v^D / (2t)
    m = eform_from_library("PZT-4")
    c33D = m.c_E[2, 2] + m.e[2, 2] ** 2 / m.eps_S[2, 2]
    f_thick_a = np.sqrt(c33D / rho) / (2 * THICKNESS)
    kt2 = m.e[2, 2] ** 2 / (c33D * m.eps_S[2, 2])
    # Thickness resonance: tan(pi/2 * fr/fa) / (pi/2 * fr/fa) = 1/kt^2 ... solved for x = fr/fa
    x = brentq(lambda x: np.tan(np.pi / 2 * x) / (np.pi / 2 * x) - 1 / kt2, 0.5, 0.99999)
    # Low-frequency (free) capacitance and its clamped counterpart
    area = np.pi * RADIUS**2
    c_free = lib["eps_T_rel"]["eps33"] * EPS0 * area / THICKNESS
    return {
        "poisson_sigma": sigma,
        "eta1": eta1,
        "f_radial_r": f_radial,
        "f_thickness_r": x * f_thick_a,
        "f_thickness_a": f_thick_a,
        "kt": np.sqrt(kt2),
        "C_free": c_free,
    }


def eigen_modes(case: str, min_charge: float = 1e-2) -> list[float]:
    """Frequencies of electrically active modes (non-negligible electrode charge)."""
    h = read_hist(case)
    # In the open-circuit case the floating electrode carries no net charge, so keep all modes.
    if case == "eigen_open":
        return [f for f in h[:, 0] if f > 1.0]
    return [f for f, q in zip(h[:, 0], h[:, 1]) if f > 1.0 and q > min_charge]


def admittance(case: str) -> tuple[np.ndarray, np.ndarray]:
    """Y = j w Q for 1 V drive on 'top' with 'bottom' grounded."""
    h = read_hist(case)
    f = h[:, 0]
    q = h[:, 1] * np.exp(1j * np.deg2rad(h[:, 2]))
    return f, 1j * 2 * np.pi * f * q


def main() -> None:
    ref = analytical()
    print("Analytical (PZT-4, a = 10.5 mm, t = 1.5 mm)")
    print(f"  Poisson ratio sigma^E      {ref['poisson_sigma']:.3f}  (eta1 = {ref['eta1']:.4f})")
    print(f"  radial f_r (thin disc)     {ref['f_radial_r'] / 1e3:8.2f} kHz")
    print(f"  thickness f_r / f_a (1D)   {ref['f_thickness_r'] / 1e3:8.1f} / {ref['f_thickness_a'] / 1e3:.1f} kHz  (k_t = {ref['kt']:.3f})")
    print(f"  free capacitance C^T       {ref['C_free'] * 1e9:8.3f} nF")

    summary: dict[str, object] = {"analytical": ref}
    for case in ("eigen_short", "eigen_open"):
        if (RUNS / case).exists():
            modes = eigen_modes(case)
            summary[case] = modes
            print(f"\n{case}: electrically active modes (kHz)")
            print("  " + ", ".join(f"{f / 1e3:.1f}" for f in modes))

    traces = []
    for case in ("harm_wide", "harm_radial", "harm_fr_fine"):
        if not (RUNS / case).exists():
            continue
        f, y = admittance(case)
        np.savetxt(
            RUNS / f"{case}_Y.csv",
            np.column_stack([f, y.real, y.imag, np.abs(y), np.angle(y, deg=True)]),
            delimiter=",",
            header="f_Hz,Re_Y_S,Im_Y_S,abs_Y_S,phase_Y_deg",
        )
        i_max, i_min = np.argmax(np.abs(y)), np.argmin(np.abs(y))
        print(f"\n{case}: {len(f)} points, {f[0] / 1e3:.1f}-{f[-1] / 1e3:.1f} kHz")
        print(f"  min Re(Y) = {y.real.min():.3e} S  (must be >= 0 for a passive device)")
        print(f"  C from Im(Y)/w at {f[0] / 1e3:.1f} kHz = {y[0].imag / (2 * np.pi * f[0]) * 1e9:.3f} nF")
        print(f"  max |Y| = {np.abs(y)[i_max]:.4e} S at {f[i_max] / 1e3:.2f} kHz")
        print(f"  min |Y| = {np.abs(y)[i_min]:.4e} S at {f[i_min] / 1e3:.2f} kHz")
        if case == "harm_fr_fine":
            # Q from the full width at half maximum of the conductance G = Re(Y): for a series
            # RLC motional branch this is exactly f_r / Q (C0 only adds to Im(Y)).
            g = y.real
            above = np.where(g >= g.max() / 2)[0]
            bw = f[above[-1]] - f[above[0]]
            print(f"  G = Re(Y) FWHM {bw:.0f} Hz -> Q ~ {f[np.argmax(g)] / bw:.0f}  (input Qm = 500)")
        traces.append({"x": f.tolist(), "y": np.abs(y).tolist(), "name": case, "type": "scatter"})

    (RUNS / "summary.json").write_text(json.dumps(summary, indent=2))
    if traces:
        html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Spike disc admittance</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script></head>
<body style="font-family:system-ui;margin:16px"><h2>PZT-4 disc, a = 10.5 mm, t = 1.5 mm: |Y(f)|, 1 V drive</h2>
<div id="p" style="height:80vh"></div><script>
Plotly.newPlot("p", {json.dumps(traces)}, {{xaxis:{{title:"f (Hz)",type:"log"}},yaxis:{{title:"|Y| (S)",type:"log"}}}});
</script></body></html>"""
        (RUNS / "admittance.html").write_text(html)
        print(f"\nwrote {RUNS}/admittance.html and *_Y.csv")


if __name__ == "__main__":
    main()
