"""생성 문서 저장 — <think>·서문 제거 후 <name>.md 로 기록.

어디에 저장하는가(out/ 루트·out/init/·out/manual/)는 러너의 경로 정책이고,
어떻게 저장하는가(정제 + UTF-8 .md)만 여기서 공용이다.
"""
from __future__ import annotations

from pathlib import Path

from ..common.textproc import strip_reasoning


def save_doc(out_dir: Path, name: str, content: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.md"
    path.write_text(strip_reasoning(content), encoding="utf-8")
    return path
