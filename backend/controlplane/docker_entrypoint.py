"""Docker runtime bootstrap for writable volumes and privilege drop."""
from __future__ import annotations

import os
import pwd
from pathlib import Path


_APP_USER = "wpipe"
_WRITABLE_DIRS = (Path("/app/out"), Path("/app/db"))


def _chown_tree(path: Path, uid: int, gid: int) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(path):
        os.chown(root, uid, gid)
        for name in dirs:
            os.chown(Path(root) / name, uid, gid)
        for name in files:
            os.chown(Path(root) / name, uid, gid)


def _prepare_volumes(uid: int, gid: int) -> None:
    if os.environ.get("WPIPE_SKIP_CHOWN", "").lower() in {"1", "true", "yes"}:
        return
    for path in _WRITABLE_DIRS:
        _chown_tree(path, uid, gid)


def _drop_privileges(user: str) -> None:
    info = pwd.getpwnam(user)
    _prepare_volumes(info.pw_uid, info.pw_gid)
    os.environ.setdefault("HOME", info.pw_dir)
    os.initgroups(user, info.pw_gid)
    os.setgid(info.pw_gid)
    os.setuid(info.pw_uid)


def main() -> int:
    if os.getuid() == 0:
        _drop_privileges(_APP_USER)

    from .app import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
