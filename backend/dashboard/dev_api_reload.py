"""Dashboard API dev runner with polling hot reload.

    python -m backend.dashboard.dev_api_reload

This intentionally stays dependency-free. It runs ``backend.dashboard.serve`` as a
child process and restarts it when relevant Python files change.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_WATCH_DIRS = [
    _ROOT / "backend" / "common",
    _ROOT / "backend" / "common_pipeline",
    _ROOT / "backend" / "dashboard",
    _ROOT / "backend" / "static_pipeline",
    _ROOT / "backend" / "manual_pipeline",
]
_SKIP_PARTS = {"__pycache__", ".venv", "node_modules", "dist"}


def _snapshot() -> dict[Path, float]:
    files: dict[Path, float] = {}
    for base in _WATCH_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in _SKIP_PARTS for part in path.parts):
                continue
            try:
                files[path] = path.stat().st_mtime
            except OSError:
                continue
    return files


def _changed(prev: dict[Path, float]) -> tuple[bool, dict[Path, float]]:
    cur = _snapshot()
    return cur != prev, cur


def _start(args: argparse.Namespace) -> subprocess.Popen:
    cmd = [
        sys.executable,
        "-m",
        "backend.dashboard.serve",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.out:
        cmd.extend(["--out", args.out])
    return subprocess.Popen(cmd, cwd=str(_ROOT))


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description="wiki-pipeline dashboard API hot reload")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--out", default=None)
    parser.add_argument("--poll", type=float, default=1.0)
    args = parser.parse_args()

    snap = _snapshot()
    proc = _start(args)
    print(f"API hot reload watching {len(snap)} files. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(args.poll)
            changed, snap = _changed(snap)
            if changed:
                print("Python change detected. Restarting dashboard API...")
                _stop(proc)
                proc = _start(args)
            if proc.poll() is not None:
                print(f"Dashboard API exited with {proc.returncode}. Restarting...")
                proc = _start(args)
    except KeyboardInterrupt:
        pass
    finally:
        _stop(proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
