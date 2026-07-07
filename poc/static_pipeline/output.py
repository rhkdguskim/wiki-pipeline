"""테마별 .md 로컬 저장 — 정적 파이프라인의 저장 경로 정책.

<think>·서문 제거는 common.textproc, MR 스텁은 common.docshub로 이동했다.
여기는 out/ 아래 어디에 어떤 이름으로 저장하는가만 남는다.
"""
from __future__ import annotations

from pathlib import Path

from ..common.textproc import strip_reasoning


def save_theme_doc(out_dir: Path, theme: str, content: str) -> Path:
    path = out_dir / f"{theme}.md"
    path.write_text(strip_reasoning(content), encoding="utf-8")
    return path


def _safe_module_name(module: str) -> str:
    """모듈 경로를 파일시스템 안전한 폴더명으로 (Src/engine -> Src__engine)."""
    return module.replace("/", "__").replace("\\", "__").replace("(root)", "_root")


def save_init_doc(out_dir: Path, module: str, theme: str, content: str) -> Path:
    """init/backfill: 모듈별 하위폴더에 테마 문서 저장 (out/init/<module>/<theme>.md)."""
    mod_dir = out_dir / "init" / _safe_module_name(module)
    mod_dir.mkdir(parents=True, exist_ok=True)
    path = mod_dir / f"{theme}.md"
    path.write_text(strip_reasoning(content), encoding="utf-8")
    return path
