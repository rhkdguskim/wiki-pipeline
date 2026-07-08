"""Strip non-ASCII bytes from migration files so alembic's cp949 configparser can read them.

Alembic 1.13 reads alembic.ini / env.py / script.py.mako / version files with
locale encoding. On a Korean Windows box, locale is cp949 and any non-ASCII
(byte > 127) raises UnicodeDecodeError. We strip non-ASCII by replacing with
ASCII transliteration or by deleting the line entirely (comments only).

Run once after adding non-ASCII comments to migration files.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


_KOREAN_RANGE = re.compile(r"[\uac00-\ud7af\u3131-\u318e]")


def _strip_non_ascii(text: str) -> str:
    """Replace non-ASCII characters with ASCII equivalents. Comments are dropped
    to keep migration files safe across locale encodings. Docstrings lose the
    non-ASCII content (English is kept)."""
    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
        elif _KOREAN_RANGE.match(ch):
            out.append("")  # drop Korean characters entirely
        else:
            # non-ASCII non-Korean ? also drop to be safe
            out.append("?")
    return "".join(out)


def process(path: Path) -> bool:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")
    if not any(b > 127 for b in raw):
        return False
    new_text = _strip_non_ascii(text)
    if new_text == text:
        return False
    path.write_text(new_text, encoding="ascii", errors="strict")
    return True


def main(roots: list[str]) -> int:
    changed = 0
    for root in roots:
        p = Path(root)
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix in {".pyc", ".pyo", ".pyd"}:
                continue
            if f.name in {"__pycache__",}:
                continue
            if process(f):
                changed += 1
                print("stripped:", f)
    print(f"changed={changed}")
    return 0


if __name__ == "__main__":
    roots = sys.argv[1:] or ["."]
    sys.exit(main(roots))
