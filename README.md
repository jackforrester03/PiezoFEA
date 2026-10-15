# PiezoFEA

Browser front end for linear piezoelectric FE simulation (2D axisymmetric discs, rings and
multilayer PTs) using [openCFS](https://opencfs.org) as the solver. See `CLAUDE.md` for the
design decisions and data model.

## Local development (macOS or Linux)

```sh
docker compose up -d --build        # backend + openCFS on http://localhost:8000
cd frontend && npm ci && npm run dev  # frontend on http://localhost:5173 (proxies /api)
```

On Linux, first create `.env` (see below) so run folders are owned by you rather than root.
Tests: `docker compose exec backend pytest -q` (add `-m "not slow"` to skip openCFS runs).

## Server (Linux, x86_64, Docker only)

```sh
git clone https://github.com/jackforrester03/PiezoFEA.git && cd PiezoFEA
printf 'COMPOSE_PROFILES=web\nPIEZOFEA_UID=%s\nPIEZOFEA_GID=%s\n' $(id -u) $(id -g) > .env
docker compose up -d --build
```

This serves the built frontend on port 8080 and the backend on 8000. Both are bound to
`127.0.0.1` only (there is no login), so open them from your own machine through an SSH tunnel:

```sh
ssh -L 8080:localhost:8080 you@server    # then browse to http://localhost:8080
```

To update: `git pull && docker compose up -d --build`. Results are kept in `data/runs/`.
