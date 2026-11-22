#!/bin/sh
# Assay container entrypoint.
#
# /out is mounted from a docker named volume, which docker creates owned by
# root. The container user (sheetsol) cannot write into a root-owned volume,
# so the entrypoint fixes ownership before dropping privileges.
#
# This script runs as root (the compose file deliberately omits `user:`, so
# the entrypoint is root); the actual workload runs as sheetsol via runuser.
# `read_only: true` only makes the root filesystem read-only — /out and /tmp
# are writable mounts, so the fix and the workload both succeed.
set -e

# Fix volume ownership only when writable; skip silently on read-only mounts.
mkdir -p /out 2>/dev/null || true
if [ -w /out ]; then
    chown -R sheetsol:sheetsol /out
    chmod 775 /out
fi

exec runuser -u sheetsol -- python -m sheet_solution "$@"