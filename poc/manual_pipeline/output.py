"""매뉴얼 .md 로컬 저장 — 매뉴얼 파이프라인의 저장 경로 정책.

<think>·서문 제거는 common.textproc, MR 스텁은 common.docshub 공용.
여기는 out/manual/ 아래 어디에 어떤 이름으로 저장하는가만 남는다.
"""
from __future__ import annotations

from pathlib import Path

from ..common.textproc import strip_reasoning


def save_manual_doc(out_dir: Path, theme_key: str, content: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{theme_key}.md"
    path.write_text(strip_reasoning(content), encoding="utf-8")
    return path
