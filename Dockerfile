# Assay Dockerfile — multi-stage, offline-capable, non-root.
# Build time (docker build) is the ONLY place network is used: wheels are
# downloaded once and vendor-baked into the final image. The final image
# needs no network and is tested with `docker run --network none`.
#
# Reused spine + packaging from Signoff 0.1.0 (see docs/archive/PROVENANCE.md).

# ---- Stage 1: builder — download pinned, hash-verified wheels --------------
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535 AS builder

COPY requirements.lock /tmp/requirements.lock
RUN mkdir -p /wheels
RUN python -m pip download --only-binary=:all: --dest /wheels \
    --require-hashes -r /tmp/requirements.lock

# ---- Stage 2: runtime — install wheels offline, run as non-root -----------
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535 AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

COPY --from=builder /wheels /wheels

# Install the application dependency set WITHOUT network access, verifying
# every wheel against the SHA-256 hashes in requirements.lock.
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --no-index --find-links /wheels \
    --require-hashes -r /app/requirements.lock \
    && rm -rf /wheels

WORKDIR /app
# pyproject declares readme + license; both must exist for an editable install.
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md
COPY LICENSE /app/LICENSE
COPY src/ /app/src/
COPY scripts/ /app/scripts/
# The `demo` spine command resolves fixtures via the /app fallback in core/cli.
COPY tests/fixtures/ /app/tests/fixtures/

# Non-root user; input mounted read-only at /data, output writable at /out.
# The container starts as root so the entrypoint can chown the /out volume
# (docker creates named volumes root-owned; a non-root user cannot chown
# them), then drops to sheetsol via runuser for the workload.
RUN useradd --create-home --shell /usr/sbin/nologin sheetsol \
    && mkdir -p /data /out \
    && chown -R sheetsol:sheetsol /app \
    && chmod 775 /out
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# No shell so no accidental network or path tricks.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
