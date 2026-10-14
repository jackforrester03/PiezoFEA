"""Job orchestration: run directory, mesh, XML, openCFS subprocesses, post-processing.

Each job lives in RUNS_DIR/<job_id>/ and keeps every input and output (the audit trail):
  project.json, status.json, mesh.msh, mat.xml, mat_lossless.xml, results.json
  eigen/            eigen.xml, cfs.log, results_hdf5/eigen.cfs
  harmonic_<port>/  one harmonic run per driven port
"""

import json
import os
import shutil
import subprocess
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel

from app.geometry.axisym import AxiModel, AxisymInterpreter
from app.mesh.gmsh_axisym import build_mesh
from app.results.charge import terminal_charges
from app.results.twoport import reciprocity_error, y_matrix
from app.schema import EigenSettings, HarmonicSettings, Project
from app.solver.xml_writer import Excitation, material_xml, simulation_xml

RUNS_DIR = Path(os.environ.get("PIEZOFEA_RUNS_DIR", "data/runs"))
MESH_FILE = "mesh.msh"
MAT_FILE = "mat.xml"
MAT_LOSSLESS_FILE = "mat_lossless.xml"

_status_lock = threading.Lock()  # sub-runs update status.json from worker threads

JobState = Literal["queued", "meshing", "solving", "postprocessing", "done", "failed"]


class JobStatus(BaseModel):
    job_id: str
    project_name: str
    state: JobState
    message: str = ""
    created: str
    updated: str
    runs: dict[str, str] = {}  # sub-run name -> queued / running / done / failed
    mesh: dict[str, Any] | None = None


class EigenResults(BaseModel):
    port_condition: Literal["short", "open"] | None
    frequencies: list[float]  # Hz, ascending, rigid-body mode removed
    port_charge: dict[str, list[float]]  # |modal charge| per port; ~0 for electrically inactive modes


class HarmonicResults(BaseModel):
    frequencies: list[float]  # Hz
    Y_real: list[list[list[float]]]  # [n_f][N][N], Y[j][k] = I_j / V_k, ports in JobResults.ports order
    Y_imag: list[list[list[float]]]
    reciprocity_error: float
    # max over runs/frequencies of |sum of all terminal charges| / max |terminal charge|; ~0 by construction
    charge_balance_error: float = 0.0


class JobResults(BaseModel):
    ports: list[str]
    eigen: EigenResults | None = None
    harmonic: HarmonicResults | None = None


class SolverError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def job_dir(job_id: str) -> Path:
    return RUNS_DIR / job_id


def read_status(job_id: str) -> JobStatus:
    return JobStatus.model_validate_json((job_dir(job_id) / "status.json").read_text())


def _write_status(status: JobStatus) -> None:
    with _status_lock:
        status.updated = _now()
        path = job_dir(status.job_id) / "status.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(status.model_dump_json(indent=2))
        tmp.replace(path)


def list_jobs() -> list[JobStatus]:
    if not RUNS_DIR.exists():
        return []
    out = [read_status(p.name) for p in RUNS_DIR.iterdir() if (p / "status.json").exists()]
    return sorted(out, key=lambda s: s.created, reverse=True)


def create_job(project: Project) -> JobStatus:
    job_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = job_dir(job_id)
    d.mkdir(parents=True)
    (d / "project.json").write_text(project.model_dump_json(indent=2))
    status = JobStatus(job_id=job_id, project_name=project.name, state="queued", created=_now(), updated=_now())
    _write_status(status)
    return status


@dataclass(frozen=True)
class SubRun:
    name: str
    analysis: EigenSettings | HarmonicSettings
    excitation: dict[str, Excitation]


def plan_runs(project: Project, model: AxiModel) -> list[SubRun]:
    """Eigen run (ports shorted or open) plus one harmonic run per port."""
    base: dict[str, Excitation] = {
        t.id: ("ground" if t.role in ("ground", "port") else "floating") for t in model.terminals
    }
    runs = []
    study = project.study
    if study.eigen:
        exc = dict(base)
        if study.eigen.port_condition == "open":
            exc.update({p: "floating" for p in model.ports})
        runs.append(SubRun("eigen", study.eigen, exc))
    if study.harmonic:
        for port in model.ports:
            exc = dict(base)
            exc[port] = "drive"
            runs.append(SubRun(f"harmonic_{port}", study.harmonic, exc))
    return runs


def _run_cfs(run_dir: Path, name: str, threads: int) -> None:
    cfs = os.environ.get("CFS_BIN") or shutil.which("cfs")
    if not cfs:
        raise SolverError("openCFS binary 'cfs' not found on PATH")
    log = run_dir / "cfs.log"
    with log.open("w") as fh:
        proc = subprocess.run(
            [cfs, "-t", str(threads), "-p", f"{name}.xml", name],
            cwd=run_dir,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    text = log.read_text(errors="replace")
    if proc.returncode != 0 or "SIMULATION RUN FAILED" in text:
        tail = "\n".join(text.strip().splitlines()[-15:])
        raise SolverError(f"openCFS run '{name}' failed (exit {proc.returncode}):\n{tail}")


def run_job(job_id: str) -> None:
    """Execute a queued job end to end. Errors end up in status.json, never raised."""
    d = job_dir(job_id)
    status = read_status(job_id)
    try:
        project = Project.model_validate_json((d / "project.json").read_text())
        model = AxisymInterpreter().interpret(project)
        runs = plan_runs(project, model)

        status.state = "meshing"
        status.runs = {r.name: "queued" for r in runs}
        _write_status(status)
        study = project.study
        f_max = study.mesh.f_max or (study.harmonic.f_stop if study.harmonic else None)
        info = build_mesh(model, study.mesh, f_max, d / MESH_FILE)
        status.mesh = {
            "element_size": info.element_size,
            "min_wavelength": info.min_wavelength,
            "num_nodes": info.num_nodes,
            "num_elements": info.num_elements,
        }
        (d / MAT_FILE).write_bytes(material_xml(model, lossless=False))
        (d / MAT_LOSSLESS_FILE).write_bytes(material_xml(model, lossless=True))

        for r in runs:
            rd = d / r.name
            rd.mkdir()
            mat = MAT_LOSSLESS_FILE if isinstance(r.analysis, EigenSettings) else MAT_FILE
            (rd / f"{r.name}.xml").write_bytes(
                simulation_xml(model, r.analysis, r.excitation, f"../{MESH_FILE}", f"../{mat}")
            )

        status.state = "solving"
        _write_status(status)
        threads = max(1, (os.cpu_count() or 1) // len(runs))

        def solve(r: SubRun) -> None:
            status.runs[r.name] = "running"
            _write_status(status)
            try:
                _run_cfs(d / r.name, r.name, threads)
            except Exception:
                status.runs[r.name] = "failed"
                raise
            status.runs[r.name] = "done"
            _write_status(status)

        with ThreadPoolExecutor(max_workers=len(runs)) as pool:
            for fut in [pool.submit(solve, r) for r in runs]:
                fut.result()

        status.state = "postprocessing"
        _write_status(status)
        results = postprocess(d, project, model, runs)
        (d / "results.json").write_text(json.dumps(results))
        status.state = "done"
        status.message = ""
        _write_status(status)
    except Exception as exc:  # noqa: BLE001 - reported to the user via status.json
        status.state = "failed"
        status.message = str(exc)
        (d / "error.log").write_text(traceback.format_exc())
        _write_status(status)


def _charges(d: Path, run: SubRun, model: AxiModel) -> tuple[np.ndarray, dict[str, np.ndarray], float]:
    """Charge on every terminal for one run, plus the relative charge balance error."""
    lossless = isinstance(run.analysis, EigenSettings)
    f, q = terminal_charges(d / run.name / "results_hdf5" / f"{run.name}.cfs", model, model.terminal_regions, lossless)
    total = np.abs(sum(q.values()))
    scale = np.max([np.abs(v) for v in q.values()], axis=0)
    balance = float(np.max(total / np.where(scale > 0, scale, 1)))
    return f, q, balance


def postprocess(d: Path, project: Project, model: AxiModel, runs: list[SubRun]) -> dict[str, Any]:
    results: dict[str, Any] = {"ports": model.ports}
    for r in runs:
        if r.name != "eigen":
            continue
        f, charges, _ = _charges(d, r, model)
        order = np.argsort(f)
        keep = [i for i in order if f[i] > 1.0]  # drop the free rigid-body z mode
        results["eigen"] = {
            "port_condition": project.study.eigen.port_condition if project.study.eigen else None,
            "frequencies": f[keep].tolist(),
            # Modal electrode charge (mode-normalised): ~0 for modes the electrodes do not excite.
            # Shorted ports carry charge; open ports do not, so then the ground terminal is used.
            "port_charge": {
                p: np.abs(charges[p][keep]).tolist()
                for p in (model.ports if project.study.eigen.port_condition == "short" else
                          [t.id for t in model.terminals if t.role == "ground"])
            },
        }
    harmonic = {r.name.removeprefix("harmonic_"): r for r in runs if r.name.startswith("harmonic_")}
    if harmonic:
        per_run = {}
        balance = 0.0
        for port, r in harmonic.items():
            f, q, b = _charges(d, r, model)
            per_run[port] = (f, q)
            balance = max(balance, b)
        f, y = y_matrix(model.ports, per_run)
        results["harmonic"] = {
            "frequencies": f.tolist(),
            "Y_real": y.real.tolist(),  # [n_f][N][N], Y[j][k] = I_j / V_k
            "Y_imag": y.imag.tolist(),
            "reciprocity_error": reciprocity_error(y),
            "charge_balance_error": balance,
        }
    return results


def read_results(job_id: str) -> JobResults:
    return JobResults.model_validate_json((job_dir(job_id) / "results.json").read_text())


def read_project(job_id: str) -> Project:
    return Project.model_validate_json((job_dir(job_id) / "project.json").read_text())
