"""테마별 .md 로컬 저장 + docs-hub MR 스텁.

M3가 응답 본문에 넣는 <think>...</think> reasoning 블록을 걷어내고 저장한다.
실제 docs-hub MR 제출은 PoC에선 스텁(로그만). DOCSHUB_MR_ENABLED=true면 훅 지점.
"""
from __future__ import annotations

import re
from pathlib import Path

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """M3의 <think> 블록 제거 후 앞뒤 공백 정리."""
    return _THINK_RE.sub("", text).strip()


def save_theme_doc(out_dir: Path, theme: str, content: str) -> Path:
    cleaned = strip_reasoning(content)
    path = out_dir / f"{theme}.md"
    path.write_text(cleaned, encoding="utf-8")
    return path


def submit_mr_stub(theme: str, path: Path, enabled: bool) -> str:
    """docs-hub MR 제출 자리. PoC는 스텁."""
    if enabled:
        return f"[MR 제출 훅] {theme}: 실제 MR API 연결 지점 (미구현)"
    return f"[MR 스텁] {theme} -> {path.name} (DOCSHUB_MR_ENABLED=false, 로컬 저장만)"
