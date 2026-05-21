#!/usr/bin/env bash
set -euo pipefail

# Usage (inside CDK bundling container):
#   bash ./scripts/bundle-lambda.sh services/hello-world
#
# Config:
#   INTERNAL_ROOTS: list of roots (relative to /asset-input) containing internal leaf packages.
#                  Each leaf package must have pyproject.toml with [project].name.

SERVICE_REL=${1:?Pass service path like services/hello-world}

ASSET_IN="/asset-input"
SERVICE_DIR="${ASSET_IN}/${SERVICE_REL}"

OUT="/asset-output"
WHEELS="/tmp/wheels"

# --- CONFIG: where to look for internal packages ---
INTERNAL_ROOTS=("packages/shared-py")
# -----------------------------------------------

rm -rf "${OUT:?}"/*
mkdir -p "$OUT" "$WHEELS"

# Build tooling in isolated venv (avoids permissions issues in CDK docker runs)
python -m venv /tmp/venv
# shellcheck disable=SC1091
source /tmp/venv/bin/activate
python -m pip install --upgrade pip
python -m pip install build wheel

# 1) Build wheels for internal workspace deps inferred from service pyproject.toml
python - "$SERVICE_DIR" "$WHEELS" "$ASSET_IN" "${INTERNAL_ROOTS[@]}" <<'PY'
import sys
from pathlib import Path
import subprocess
import tomllib
import re

service_dir = Path(sys.argv[1])
wheel_dir = Path(sys.argv[2])
asset_in = Path(sys.argv[3])
internal_roots = [asset_in / p for p in sys.argv[4:]]

pyproject = service_dir / "pyproject.toml"
if not pyproject.exists():
    raise SystemExit(f"Missing {pyproject}")

data = tomllib.loads(pyproject.read_text("utf-8"))

def dep_name(spec: str) -> str:
    s = spec.strip().split(";", 1)[0].strip()
    # get leading distribution name token (handles foo, foo>=1, foo[extra]>=1)
    m = re.match(r"^([A-Za-z0-9_.-]+)", s)
    return m.group(1) if m else s

deps_raw = (data.get("project", {}) or {}).get("dependencies", []) or []
deps = {dep_name(x) for x in deps_raw if isinstance(x, str) and x.strip()}

sources = (data.get("tool", {}).get("uv", {}).get("sources", {}) or {})
workspace = {name for name, cfg in sources.items()
             if isinstance(cfg, dict) and cfg.get("workspace") is True}

internal = sorted(deps & workspace)
if not internal:
    sys.exit(0)

# Map [project].name -> folder by scanning internal roots
name_to_path: dict[str, Path] = {}
for root in internal_roots:
    if not root.exists():
        continue
    for child in root.iterdir():
        pp = child / "pyproject.toml"
        if child.is_dir() and pp.exists():
            pkg = tomllib.loads(pp.read_text("utf-8"))
            pname = (pkg.get("project", {}) or {}).get("name")
            if isinstance(pname, str) and pname:
                name_to_path[pname] = child

missing = [d for d in internal if d not in name_to_path]
if missing:
    raise SystemExit(
        "Internal deps declared in service pyproject.toml not found under internal roots:\n"
        + "\n".join(f"  - {m}" for m in missing)
        + "\n\nEnsure each internal package has pyproject.toml with [project].name matching the dependency string."
    )

wheel_dir.mkdir(parents=True, exist_ok=True)
for dep in internal:
    pkg_path = name_to_path[dep]
    print(f"Building internal wheel: {dep} from {pkg_path}", file=sys.stderr)
    subprocess.check_call([sys.executable, "-m", "build", str(pkg_path), "--wheel", "--outdir", str(wheel_dir)])
PY

# 2) Install internal wheels into /asset-output
if compgen -G "$WHEELS"/*.whl > /dev/null; then
  python -m pip install --upgrade --no-deps --target "$OUT" "$WHEELS"/*.whl
fi

# 3) Install third-party deps (must be no-editable / no local paths)
REQ="$SERVICE_DIR/requirements.lambda.txt"
if [ -f "$REQ" ]; then
  python -m pip install --upgrade --target "$OUT" -r "$REQ"
else
  echo "Warning: $REQ not found; skipping third-party deps" >&2
fi

# 4) Copy service code into /asset-output
if [ -d "$SERVICE_DIR/src" ]; then
  cp -R "$SERVICE_DIR/src/"* "$OUT/"
else
  # Copy the service dir (excluding common junk)
  rsync -a \
    --exclude "__pycache__" \
    --exclude ".venv" \
    --exclude ".pytest_cache" \
    --exclude ".mypy_cache" \
    --exclude ".ruff_cache" \
    --exclude "node_modules" \
    --exclude ".git" \
    --exclude "dist" \
    --exclude "build" \
    --exclude "*.egg-info" \
    "$SERVICE_DIR"/ "$OUT"/
fi

# 5) Cleanup without relying on `find`
python - <<'PY'
import os, shutil
root="/asset-output"
for dirpath, dirnames, _ in os.walk(root):
    if "__pycache__" in dirnames:
        shutil.rmtree(os.path.join(dirpath, "__pycache__"), ignore_errors=True)
PY

