#!/usr/bin/env bash
# Assay — build a standalone, offline release bundle.
#
# Produces dist/assay-<version>.bundle.tar.gz containing:
#   - the wheel (pip-installable)
#   - a vendored offline wheel set (so install works with no network)
#   - run.sh + the GUI launcher
#   - user-facing docs (README, USER-GUIDE, template example)
#   - a release-notes file
#
# The bundle is what you "send to different people": drop it on their
# machine, run the included install step (offline), and use it. No cloud,
# no hardware requirements beyond Python 3.11+ (or the bundled venv).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(python3 -c 'import tomllib,sys; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
OUT="dist"
BUNDLE="$OUT/assay-${VERSION}.bundle"
WHEEL="$OUT/assay-${VERSION}-py3-none-any.whl"

rm -rf "$OUT" "$BUNDLE"
mkdir -p "$BUNDLE/vendor/wheels" "$OUT"

# Build tooling lives in a throwaway venv so we never touch system packages
# (works on PEP-668 "externally managed" hosts and plain hosts alike).
BUILD_VENV=".build-venv"
python3 -m venv "$BUILD_VENV"
BPY="$BUILD_VENV/bin/python"
"$BPY" -m pip install --quiet --upgrade pip build
"$BPY" -m build --wheel --outdir "$OUT" .

echo ">> vendoring offline wheels (for no-network installs)"
# The canonical hash-anchored install path is the Docker image (Python 3.11,
# matching requirements.lock). The pip-bundle vendors wheels for the build
# host's Python; hashes are recorded for reference but the host-platform
# wheel may differ, so we do not enforce --require-hashes here (Docker does).
"$BPY" -m pip download --only-binary=:all: --dest "$BUNDLE/vendor/wheels" \
    fpdf2==2.8.8 openpyxl==3.1.5 2>/dev/null \
  || "$BPY" -m pip download --only-binary=:all: --dest "$BUNDLE/vendor/wheels" \
       fpdf2 openpyxl
# Optional GUI extra (flask + its transitive deps) so the GUI works offline.
"$BPY" -m pip download --only-binary=:all: --dest "$BUNDLE/vendor/wheels" \
    "flask==3.0.3" 2>/dev/null || true

echo ">> assembling bundle"
cp "$OUT"/*.whl "$BUNDLE/"
# Include the lock file where install.sh expects it for offline installs.
cp requirements.lock "$BUNDLE/vendor/wheels/requirements.lock"
cp run.sh install.sh gui.sh "$BUNDLE/"
chmod +x "$BUNDLE/run.sh" "$BUNDLE/install.sh" "$BUNDLE/gui.sh"
cp -r gui "$BUNDLE/gui"
cp README.md SECURITY.md LICENSE PROVENANCE.md "$BUNDLE/"
mkdir -p "$BUNDLE/docs" "$BUNDLE/examples"
cp docs/USER-GUIDE.md docs/ARCHITECTURE.md "$BUNDLE/docs/"
cp examples/check-template.example.txt "$BUNDLE/examples/"

# A one-line release note.
cat > "$BUNDLE/RELEASE-NOTES.md" <<EOF
Assay v${VERSION}
$(date -u +%Y-%m-%dT%H:%M:%SZ)

Deterministic, offline sheet-audit platform. See USER-GUIDE.md (plain
English) for how to use it. Nothing leaves your machine.
EOF

echo ">> packaging"
tar -czf "$BUNDLE.tar.gz" -C "$OUT" "$(basename "$BUNDLE")"
rm -rf "$BUNDLE" "$BUILD_VENV"

echo
echo "Release bundle: $BUNDLE.tar.gz"
echo "  wheel:        $WHEEL"
echo "  Contents: wheel + offline wheels + run.sh + gui + docs + template"
echo
echo "To ship to a recipient: send the .tar.gz; they extract and run:"
echo "  tar xzf $BUNDLE.tar.gz && cd $(basename "$BUNDLE") && ./run.sh <sheet> <template>"
