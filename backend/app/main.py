"""FastAPI app and routes."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from app.geometry.axisym import AxisymInterpreter
from app.geometry.base import InterpreterError
from app.materials.convert import list_library
from app.schema import Project
from app.solver import runner
from app.solver.runner import JobResults, JobStatus

app = FastAPI(title="PiezoFEA")


VALIDATION_DIR = Path(os.environ.get("PIEZOFEA_VALIDATION_DIR", "/validation"))


class MaterialSummary(BaseModel):
    id: str
    name: str
    source: str


class Example(BaseModel):
    id: str
    project: Project


@app.get("/api/health")
def health() -> dict[str, object]:
    """Report backend status and whether the openCFS binary is reachable."""
    cfs_path = shutil.which("cfs")
    cfs_ok = False
    if cfs_path:
        try:
            proc = subprocess.run([cfs_path, "-h"], capture_output=True, text=True, timeout=60)
            cfs_ok = proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            cfs_ok = False
    return {"status": "ok", "cfs_path": cfs_path, "cfs_ok": cfs_ok}


@app.get("/api/materials")
def materials() -> list[MaterialSummary]:
    return [MaterialSummary(**m) for m in list_library()]


@app.get("/api/examples")
def examples() -> list[Example]:
    """Validation cases (validation/<case>/project.json), usable as starting templates."""
    if not VALIDATION_DIR.exists():
        return []
    return [
        Example(id=p.parent.name, project=Project.model_validate_json(p.read_text()))
        for p in sorted(VALIDATION_DIR.glob("*/project.json"))
    ]


@app.post("/api/jobs", status_code=202)
def submit_job(project: Project, background: BackgroundTasks) -> JobStatus:
    """Validate the project for the axisymmetric solver, then mesh and solve in the background."""
    try:
        AxisymInterpreter().interpret(project)
    except InterpreterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    status = runner.create_job(project)
    background.add_task(runner.run_job, status.job_id)
    return status


@app.get("/api/jobs")
def jobs() -> list[JobStatus]:
    return runner.list_jobs()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> JobStatus:
    if not re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{6}", job_id) or not (runner.job_dir(job_id) / "status.json").exists():
        raise HTTPException(status_code=404, detail="unknown job")
    return runner.read_status(job_id)


@app.get("/api/jobs/{job_id}/results")
def job_results(job_id: str) -> JobResults:
    status = job_status(job_id)
    if status.state != "done":
        raise HTTPException(status_code=409, detail=f"job is {status.state}")
    return runner.read_results(job_id)


@app.get("/api/jobs/{job_id}/project")
def job_project(job_id: str) -> Project:
    job_status(job_id)  # validates the id
    return runner.read_project(job_id)
