# openCFS ships an x86_64 Linux binary. On Apple Silicon this runs under emulation.
FROM --platform=linux/amd64 python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates libgomp1 \
        libgl1 libglu1-mesa libxrender1 libxcursor1 libxft2 libxinerama1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# openCFS prebuilt binary, pinned release (bump deliberately; see CLAUDE.md)
ARG CFS_VERSION=2026W
WORKDIR /opt
RUN wget -q https://gitlab.com/openCFS/cfs/-/releases/${CFS_VERSION}/downloads/CFS-Linux.tar.gz \
    && tar -xzf CFS-Linux.tar.gz && rm CFS-Linux.tar.gz \
    && ln -s /opt/CFS-*-Linux /opt/cfs \
    # 2026W packaging bug: CFS.xsd includes CFS_PDEmagneticScalarPotentialAdj.xsd but the file
    # ships without the CFS_ prefix. Without it, openCFS silently skips schema validation.
    && ln -s PDEmagneticScalarPotentialAdj.xsd \
        /opt/cfs/share/xml/CFS-Simulation/Schemas/CFS_PDEmagneticScalarPotentialAdj.xsd
ENV PATH="/opt/cfs/bin:${PATH}"

# Install dependencies only (from pyproject) so this layer caches independently of app code.
WORKDIR /app
COPY pyproject.toml .
RUN python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb'))['project']; print('\n'.join(d['dependencies'] + d['optional-dependencies']['dev']))" > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt
COPY app ./app
COPY tests ./tests

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
