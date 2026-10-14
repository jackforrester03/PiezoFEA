# PiezoFEA — web front end for openCFS piezoelectric simulation

## What this project is

A browser-based tool for setting up, running and post-processing linear piezoelectric
FE simulations, using **openCFS** (open-source, TU Wien/Graz/FAU) as the solver.
The aim is a COMSOL-like workflow for the problems the owner actually runs: mostly
**2D axisymmetric piezoelectric transformers and resonators** (discs and rings with
radial electrode bands), with full 3D added later as a separate solver path.

Owner: an academic in power electronics who works on piezoelectric transformers (PTs) and
resonant converters. He knows the physics well; explain software decisions, not piezo theory.

**Flow:** define geometry, electrodes and materials in the browser → backend builds the Gmsh
mesh and openCFS XML → run openCFS in Docker → parse HDF5 results → show admittance spectra
and mode shapes → export two-port data and SPICE models.

openCFS is the solver only. Everything in this repo is the wrapper: input generation,
orchestration, post-processing and circuit export.

## Guiding decisions (do not change without asking)

1. **2D axisymmetric first.** It must work end to end before any 3D work starts.
2. **The data model is independent of dimension.** Electrodes are regions on surfaces with a
   terminal ID. They are never "radial bands" in the core schema. The axisymmetric path is
   one *interpreter* that collapses the model to the r–z cross-section. 3D comes later as a
   second interpreter. The UI, materials, two-port extraction and export must not assume
   axisymmetry.
3. **Circuits are handled outside openCFS.** We extract N-port admittance Y(f) from harmonic
   FE runs and combine loads and sources analytically or in SPICE. Do not try to put lumped
   circuits inside openCFS.
4. **Docker for the solver and backend.** Use the prebuilt openCFS Linux binary, not a
   source build.
5. **The backend is Python/FastAPI.** The frontend is React + TypeScript (Vite), Plotly for
   2D plots and vtk.js for field and mode-shape views.

## Repository layout

```
piezofea/
├── CLAUDE.md
├── docker-compose.yml
├── .gitignore                  # include data/runs/, node_modules/, __pycache__/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py             # FastAPI app, routes
│   │   ├── schema.py           # Pydantic models: Project, Body, Electrode, Material, Study
│   │   ├── materials/
│   │   │   ├── convert.py      # d-form <-> e-form, losses, rotation
│   │   │   └── library/        # JSON material files (PZT-4, PZT-5A, PZT-8, ...)
│   │   ├── geometry/
│   │   │   ├── base.py         # interface for interpreters
│   │   │   └── axisym.py       # 2D axisymmetric interpreter
│   │   ├── mesh/
│   │   │   └── gmsh_axisym.py  # Gmsh Python API, physical groups per region/electrode
│   │   ├── solver/
│   │   │   ├── xml_writer.py   # openCFS simulation + material XML
│   │   │   └── runner.py       # run dirs, subprocess, status, logs
│   │   ├── results/
│   │   │   ├── reader.py       # HDF5 (.cfs) parsing
│   │   │   ├── admittance.py   # charge -> current -> Y(f)
│   │   │   └── twoport.py      # N-port extraction from multiple runs
│   │   └── export/
│   │       ├── touchstone.py   # .yNp / .sNp via scikit-rf
│   │       └── spice.py        # vector fit -> SPICE subcircuit
│   └── tests/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── components/         # GeometryEditor, ElectrodeEditor, MaterialPanel, StudyPanel,
│       │                       # AdmittancePlot, ModeViewer, ExportPanel
│       └── api/
├── validation/                 # reference cases (analytical + COMSOL exports)
└── data/runs/                  # one folder per job (gitignored)
```

## Environment setup

### Prerequisites
- Docker (Docker Desktop on macOS/Windows) with docker compose
- Node 20+ for local frontend development (or run the frontend in a container too)
- Git

### Backend Dockerfile (starting point)

```dockerfile
# openCFS ships an x86_64 Linux binary. On Apple Silicon this runs under emulation.
FROM --platform=linux/amd64 python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates libgomp1 \
        libglu1-mesa libxrender1 libxcursor1 libxft2 libxinerama1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# openCFS prebuilt binary (latest release permalink)
WORKDIR /opt
RUN wget -q https://gitlab.com/openCFS/cfs/-/releases/permalink/latest/downloads/CFS-Linux.tar.gz \
    && tar -xzf CFS-Linux.tar.gz && rm CFS-Linux.tar.gz \
    && ln -s /opt/CFS-*-Linux /opt/cfs
ENV PATH="/opt/cfs/bin:${PATH}"

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

The first build step is to check that `cfs -h` runs inside the container. Pin the openCFS
release version once a working one is confirmed, for reproducibility.

### Python dependencies (pyproject.toml)
- fastapi, uvicorn[standard], pydantic>=2
- gmsh (pip wheel includes the Python API)
- numpy, scipy, h5py
- lxml (XML generation)
- scikit-rf (Touchstone I/O, VectorFitting, SPICE subcircuit export)
- pyCFS (official openCFS Python tools; evaluate whether it simplifies HDF5 reading)
- pytest

### Frontend
`npm create vite@latest frontend -- --template react-ts`, then add `plotly.js` +
`react-plotly.js`, `@kitware/vtk.js`, and a small state store (zustand).
As built: `plotly.js-dist-min` + `react-plotly.js/factory`. API types are generated, never
hand-written: with the backend running, `npm run gen:api` writes `src/api/schema.d.ts`
(openapi-typescript is run via npx because it pins a TypeScript 5 peer dependency).

### docker-compose.yml
- `backend`: build ./backend, port 8000, mount `./backend/app` (hot reload) and `./data`.
- `frontend`: either run locally with `npm run dev` (proxy /api → localhost:8000) or add a
  node service. Local dev is fine to start with.

## Core data model (schema.py)

```
Project
  name, units (SI throughout internally)
  bodies: [Body]
  electrodes: [Electrode]
  terminals: [Terminal]          # electrodes sharing a terminal are tied together
  study: Study

Body
  id, shape (template: "disc" | "ring" | later "polygon_revolve", "box", ...)
  params (e.g. radius, inner_radius, thickness, z_offset)
  material_id
  poling: { direction: unit vector in global frame, or "+z" / "-z" / "radial" }

Electrode
  id, body_id, surface ("top" | "bottom" | "outer" | "inner" | later arbitrary face ref)
  extent: a shape on that surface. In axisym: [r_min, r_max]. Store generally, e.g.
          { "kind": "annulus", "r_min": ..., "r_max": ..., "theta_min": 0, "theta_max": 360 }
          so azimuthal segments are representable later. The axisym interpreter rejects
          non-full theta ranges with a clear error.
  terminal_id

Terminal
  id, name, role ("port" | "ground" | "floating")

Study                            # eigen and/or harmonic (at least one); both run in one job
  eigen: { num_modes, freq_shift, port_condition: "short" | "open" }   # optional
  harmonic: { f_start, f_stop, n_points, spacing: "lin" | "log" }        # optional
  ports: list of terminal_ids to excite (for N-port extraction; empty = all "port" terminals)
  mesh: { max_element_size, elements_per_wavelength_at_f_max, f_max, order: 1 | 2 }
```

As implemented (`backend/app/schema.py`): bodies are a discriminated union on `shape`;
`extent` is `annulus` (top/bottom, absolute r) or `band` (outer/inner, z from the body's bottom
face). Poling `-z` is handled exactly by negating e (6mm symmetry), not by matRotation. Gmsh
physical groups are `body_<id>`, `term_<id>` (all electrode curves of a terminal, so BCs and
floating constraints are per terminal; each curve is in exactly one group) and `axis`. Not yet
supported, and rejected with a clear error: radial/vector poling.

Multilayer stacks are several Bodies stacked in z, with internal electrodes at the
interfaces. Design for this from the start, because it is common in PTs.

## Materials (materials/convert.py)

Users enter **datasheet d-form** values. Convert to the e-form that openCFS needs:

- Input: s^E (6×6 compliance), d (3×6), ε^T (3×3 relative or absolute; be explicit),
  ρ, plus losses: mechanical Qm, dielectric tan δ, optional piezo loss.
- c^E = (s^E)^-1
- e = d · c^E
- ε^S = ε^T − d · c^E · dᵀ
- Use **IEEE Voigt ordering** (xx, yy, zz, yz, xz, xy) internally. Be careful: COMSOL and some
  datasheets differ. Document the ordering in the material JSON.
- Poling: material constants are given with poling along local 3. Rotate to the global frame
  using openCFS `<matRotation alpha beta gamma/>` on the region, rather than rotating tensors
  ourselves, if that works in axisym. Verify.
- Losses: check whether openCFS supports complex material coefficients in harmonic analysis
  or only Rayleigh damping. Prefer complex: c(1 + j/Qm), ε(1 − j tan δ). If only Rayleigh is
  available, fit α/β so that Q matches Qm at the operating frequency and record that this is
  an approximation.
- Unit tests: round-trip d → e → d, and check ε^S against a published PZT-4 / PZT-5A dataset.

Ship a small JSON library: PZT-4, PZT-5A, PZT-5H, PZT-8, and leave room for user materials.

## openCFS integration (solver/)

The openCFS docs are thin, so **verify every XML element name against the docs and the
openCFS test suite before relying on it.** Do not guess. Useful references:

- Install: https://opencfs.gitlab.io/userdocu/Installation/CFS/
- Piezo PDE (coupling block, material tensor format, matRotation, analysis types):
  https://opencfs.gitlab.io/userdocu/PDEExplanations/Coupledfield/PiezoelectricPDE/
- Electrostatic PDE (potential / ground / charge BCs, electrode handling):
  https://opencfs.gitlab.io/userdocu/PDEExplanations/Singlefield/ElectrostaticPDE/
- Piezo unit-cube tutorial (complete working XML + material file — start from this):
  https://opencfs.gitlab.io/userdocu/Tutorials/Piezo_UnitCube/
- Gmsh meshing for openCFS: https://opencfs.gitlab.io/userdocu/Tutorials/Meshing/Gmsh/
- Python post-processing / pyCFS: https://opencfs.gitlab.io/userdocu/PostProcessing/PythonPostProcessing/
- Test suite (many real XML examples): https://gitlab.com/openCFS/Testsuite

Known structure: mechanic PDE + electrostatic PDE in `<pdeList>`, coupled by
`<couplingList><direct><piezoDirect>` over the piezo regions. The analysis types are
`<static/>`, `<transient>`, `<harmonic>` (frequency list), and `<eigenFrequency>`.

To confirm early, in a spike before building the UI (spike: `validation/spike_disc/`, openCFS
2026W, PZT-4 disc a = 10.5 mm, t = 1.5 mm):
- [x] Axisymmetric: `<domain geometryType="axi">` and `<mechanic subType="axi">`. Mesh x = r,
      y = z. Fix `<comp dof="r"/>` on the axis.
- [x] Material tensors are given in standard 3D IEEE Voigt order with poling along 3, and the
      axi solver maps 3 → z itself (no matRotation needed for ±z poling). Verified: radial f_r
      109.0 kHz FE vs 109.24 kHz thin-disc theory.
- [x] Equipotential floating electrode: `<constraint name="..."/>` in electrostatic bcsAndLoads.
      Verified: open-circuit eigen f_a = 125.9 kHz = harmonic |Y| minimum 125.90 kHz.
- [x] Electrode charge. **We do not use openCFS's elecCharge for results.** For an electrode
      between two bodies it integrates one side only and ignores `neighborRegion` (it gave the
      same value for lower/upper/both; nodal `elecRhsLoad` is just the applied load, zero).
      `results/charge.py` instead computes the weak-form reaction charge
      Q = −∫∇w·D dV from the stored u and φ (w = 1 on the terminal's nodes). It is two-sided,
      sums to zero over all terminals, and matches elecCharge on outer electrodes to 5e-6.
      Original finding: `<surfRegionResult type="elecCharge">` with
      `<surfRegion name="top" neighborRegion="piezo"/>` under piezoDirect storeResults. It is the
      full revolved charge (2πr included): C at 20 kHz = 2.682 nF vs C^T = 2.658 nF. Written as
      text to `history/<run>-elecCharge-surfRegion-<name>.hist` (f, amplitude, phase in degrees)
      as well as to the HDF5 (HDF5 layout not yet inspected).
- [x] Sweep: `<harmonic><numFreq/><startFreq/><stopFreq/><sampling>linear|log|reverseLog`.
- [x] Complex materials: `complexMaterial="yes"` on the region in mechanic, electrostatic and
      piezoDirect, with `<imag>` holding the absolute imaginary part. Convention: c(1 + j/Qm),
      ε(1 − j tanδ) gives Re(Y) > 0 and Q = 519 for Qm = 500 (the lossless e adds stiffness).
- [~] Runtime: 84×12 quad8 mesh, under amd64 emulation on Apple Silicon: eigen (60 modes)
      ~4 s; harmonic ~0.6 s per frequency (300 points ≈ 190 s). Memory not yet measured.

openCFS gotchas found:
- XML comments before the root element make openCFS fail with "document root has 2 children"
  (in both simulation and material files).
- The 2026W package has a broken schema include (`CFS_PDEmagneticScalarPotentialAdj.xsd`).
  Without the symlink in the Dockerfile, openCFS warns once and silently skips schema validation.

**Spike task:** hand-write the XML for a single PZT disc with full-face electrodes (axisym),
run eigen + harmonic, and recover the radial and thickness resonances. Only then generalise
into `xml_writer.py`.

### Runner
- Each job gets `data/runs/<job_id>/` holding the mesh, XML, material file, stdout/stderr
  log, and result .cfs/HDF5.
- Run `cfs` with subprocess, store status in a small JSON file in the run dir, and poll from
  the frontend. Use FastAPI BackgroundTasks for now and add a queue later if needed.
- N-port extraction means N harmonic runs (one per driven port). Run them in parallel if
  cores allow.

## Meshing (mesh/gmsh_axisym.py)

- Build the r–z cross-section with the Gmsh OCC kernel. Split boundary curves at electrode
  r_min/r_max so each electrode is its own curve.
- Physical groups: one per body (volume/surface region with material), one per electrode
  (boundary), plus the symmetry axis.
- Size control: user max size plus an automatic limit from wavelength at f_max (e.g. ≥10
  quadratic elements per wavelength of the slowest relevant wave). Refine at electrode edges.
- Export in a format openCFS reads directly (check the Gmsh tutorial; `.msh` v2 or v4).

## Results and post-processing (results/)

- Current from charge: I = jω Q on each port terminal.
- **Y-parameters:** drive port k at V_k = 1 V with all other ports at 0 V (shorted to ground),
  so Y_jk = I_j / V_k. N runs → full N×N Y(f). Check reciprocity Y_jk ≈ Y_kj as a sanity test.
- Derived quantities: impedance magnitude and phase, resonance/antiresonance fr/fa, k_eff²,
  Qm from the -3 dB width, and voltage gain into a user-specified load.
- **Loads are computed analytically:** for a 2-port with load Y_L on port 2,
  gain = −Y21 / (Y22 + Y_L), input admittance = Y11 − Y12·Y21/(Y22 + Y_L).
  Do this in the frontend (or a fast endpoint) so changing the load needs no re-solve.
- Mode shapes from eigen runs: deformed mesh + colour by displacement/potential in vtk.js,
  animated. For axisym, show the cross-section and optionally a revolved 3D view.

## Export (export/)

Milestone 1:
- CSV of f, Y_jk (real/imag), Z, gain.
- Touchstone (`.y2p` / `.s2p`) via scikit-rf.

Milestone 2:
- Vector fitting (`skrf.vectorFitting.VectorFitting`) with a passivity check and enforcement
  → `write_spice_subcircuit_s` for a SPICE netlist. Validate by simulating the netlist in
  ngspice and comparing to the FE Y(f).
- An optional fitted multi-branch BVD equivalent circuit (familiar and readable for PT work).
- This is what enables non-sinusoidal and switching-converter simulation: Fourier/harmonic
  superposition for periodic drive, and time-domain SPICE for switches/rectifiers. It is
  valid only while the PT stays linear.

## Validation (validation/)

No feature is "done" until checked against a reference:
1. **Analytical:** thin-disc radial mode f_r ≈ η₁ / (2πa) · √(1 / (ρ s11^E (1 − σ²))) and
   thickness mode f ≈ N_t / t for the material used. Check mesh convergence.
2. **COMSOL:** the owner will supply a COMSOL disc/PT model (geometry, material constants,
   admittance sweep). Overlay the spectra and report fr/fa and peak |Y| error.
3. **Reciprocity** and **passivity** of the extracted Y(f).
Keep each case as a saved Project JSON plus reference data, run from pytest.

## Milestones

1. **Environment:** Docker image builds, `cfs -h` runs, FastAPI health endpoint, Vite app
   talks to the backend.
2. **Solver spike:** hand-written axisym disc XML runs; resolve the checklist above.
3. **Backend vertical slice:** Project JSON → materials → Gmsh → XML → run → HDF5 → Y(f) for
   a single-port disc. Validated analytically.
4. **Frontend slice:** disc template editor with electrode bands and terminals, material
   picker, study panel, run/status, admittance plot.
5. **Two-port PTs:** multi-electrode and multilayer, N-port extraction, load/gain analysis,
   COMSOL comparison.
6. **Mode viewer + export:** vtk.js modes, CSV/Touchstone, then vector-fit SPICE export.
7. **Later:** sweeps/parametric studies, saved projects, thermal loop, 3D interpreter
   (azimuthal electrode segments).

## Conventions

- SI units internally; convert only at the UI edge (mm, kHz shown in the UI).
- Type hints everywhere. The Pydantic schema is the single source of truth, and the
  frontend TS types are generated from the FastAPI OpenAPI schema.
- Every physics conversion has a unit test with a known published value.
- Never silently guess an openCFS behaviour. If a docs check is inconclusive, write a tiny
  test case and run it.
- Keep the run directories: they are the audit trail for any plotted number.
