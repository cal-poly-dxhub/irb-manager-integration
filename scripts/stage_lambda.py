#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def dep_name(spec: str) -> str:
    """
    Extract a dependency name from a PEP 508-ish string.
    Good enough for internal deps like "say-hello" or "say-hello>=0.1.0".
    """
    s = spec.strip()
    # strip environment markers
    s = s.split(";", 1)[0].strip()
    # take up to first version/operator/space
    m = re.match(r"^([A-Za-z0-9_.-]+)", s)
    return m.group(1) if m else s


def load_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text("utf-8"))


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python scripts/stage_lambda.py services/hello-world",
            file=sys.stderr,
        )
        return 2

    service_rel = Path(sys.argv[1])
    repo_root = Path(__file__).resolve().parents[1]

    service_dir = repo_root / service_rel
    service_pyproject = service_dir / "pyproject.toml"
    if not service_pyproject.exists():
        print(f"Missing {service_pyproject}", file=sys.stderr)
        return 2

    service_name = service_rel.name
    stage_dir = repo_root / "apps" / "infra" / "dist" / "stage" / service_name

    # fresh stage
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    # include shared bundler script
    (stage_dir / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        repo_root / "scripts" / "bundle-lambda.sh",
        stage_dir / "scripts" / "bundle-lambda.sh",
    )

    # include service folder
    (stage_dir / service_rel.parent).mkdir(parents=True, exist_ok=True)
    shutil.copytree(service_dir, stage_dir / service_rel, dirs_exist_ok=True)

    data = load_toml(service_pyproject)
    deps_raw = (data.get("project", {}) or {}).get("dependencies", []) or []
    deps = {dep_name(x) for x in deps_raw if isinstance(x, str) and x.strip()}

    sources = ((data.get("tool", {}) or {}).get("uv", {}) or {}).get(
        "sources", {}
    ) or {}
    workspace_sources = {
        name
        for name, cfg in sources.items()
        if isinstance(cfg, dict) and cfg.get("workspace") is True
    }

    internal = sorted(deps & workspace_sources)

    # map project.name -> package dir by scanning known internal roots
    internal_roots = [
        repo_root / "packages" / "shared-py",
        # add more roots here if needed
    ]

    name_to_path: dict[str, Path] = {}
    for root in internal_roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            pp = child / "pyproject.toml"
            if child.is_dir() and pp.exists():
                try:
                    pkg = load_toml(pp)
                except Exception:
                    continue
                pname = (pkg.get("project", {}) or {}).get("name")
                if isinstance(pname, str) and pname:
                    name_to_path[pname] = child

    missing = [d for d in internal if d not in name_to_path]
    if missing:
        print(
            "Internal workspace deps not found under packages/shared-py/*:\n"
            + "\n".join(f"  - {m}" for m in missing),
            file=sys.stderr,
        )
        return 2

    # copy only required internal packages into stage
    for dep in internal:
        src = name_to_path[dep]
        rel = src.relative_to(repo_root)
        dst = stage_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)

    print(f"Staged: {stage_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
