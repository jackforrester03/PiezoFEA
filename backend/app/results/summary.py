"""Print key numbers for a finished job and write impedance.html into its run directory.

Usage (in the backend container): python -m app.results.summary [job_id]   (default: latest job)
"""

import json
import sys

import numpy as np

from app.solver import runner


def main(job_id: str | None) -> None:
    if job_id is None:
        jobs = runner.list_jobs()
        if not jobs:
            sys.exit("no jobs found")
        job_id = jobs[0].job_id
    status = runner.read_status(job_id)
    print(f"job {job_id}: {status.project_name} [{status.state}]")
    if status.mesh:
        print(f"  mesh: {status.mesh['num_elements']} elements, {status.mesh['num_nodes']} nodes, "
              f"h = {status.mesh['element_size'] * 1e3:.3f} mm")
    if status.state != "done":
        print(f"  {status.message}")
        return
    r = runner.read_results(job_id).model_dump(exclude_none=True)
    ports = r["ports"]

    if "eigen" in r:
        e = r["eigen"]
        f = np.array(e["frequencies"])
        q = np.max([np.array(v) for v in e["port_charge"].values()], axis=0)
        active = f[q > 1e-2 * q.max()] if q.max() > 0 else f
        print(f"  eigen ({e['port_condition']}): {len(f)} modes, electrically active (kHz):")
        print("    " + ", ".join(f"{x / 1e3:.2f}" for x in active))

    if "harmonic" in r:
        h = r["harmonic"]
        f = np.array(h["frequencies"])
        y = np.array(h["Y_real"]) + 1j * np.array(h["Y_imag"])
        print(f"  harmonic: {len(f)} points, {f[0] / 1e3:.1f}-{f[-1] / 1e3:.1f} kHz, "
              f"reciprocity error {h['reciprocity_error']:.2e}")
        y11 = y[:, 0, 0]
        i_max, i_min = np.argmax(np.abs(y11)), np.argmin(np.abs(y11))
        print(f"  Y11 ({ports[0]}): C at {f[0] / 1e3:.1f} kHz = {y11[0].imag / (2 * np.pi * f[0]) * 1e9:.3f} nF")
        print(f"    max |Y| {np.abs(y11[i_max]):.3e} S at {f[i_max] / 1e3:.2f} kHz;"
              f" min |Y| {np.abs(y11[i_min]):.3e} S at {f[i_min] / 1e3:.2f} kHz")
        print(f"    min Re(Y11) = {y11.real.min():.3e} S (>= 0 for a passive device)")

        z = np.linalg.inv(y)  # open-circuit impedance parameters; 1/Y for a single port
        traces = [
            {"x": f.tolist(), "y": np.abs(z[:, j, k]).tolist(), "name": f"|Z{j + 1}{k + 1}|", "type": "scatter"}
            for j in range(len(ports))
            for k in range(len(ports))
        ]
        html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{status.project_name}</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script></head>
<body style="font-family:system-ui;margin:16px"><h2>{status.project_name}</h2><p>job {job_id}</p>
<div id="p" style="height:75vh"></div><script>
Plotly.newPlot("p", {json.dumps(traces)}, {{xaxis:{{title:"f (Hz)"}},yaxis:{{title:"|Z| (Ω)",type:"log"}}}});
</script></body></html>"""
        out = runner.job_dir(job_id) / "impedance.html"
        out.write_text(html)
        print(f"  plot: data/runs/{job_id}/impedance.html")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
