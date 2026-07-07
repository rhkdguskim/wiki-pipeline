"""매뉴얼 라이프사이클 판정 — ADD / UPDATE / DELETE 후보(deprecated 유예).

decision-commit-history-manual-diff: ADD/UPDATE/DELETE는 커밋 히스토리와 관측 두 신호의
교차로 판정한다. PoC는 커밋 히스토리 신호가 없으므로(앱 소스 레포 미연결) 단순화한다:
- ADD / UPDATE: 기존 문서 파일 유무 (이번 관측으로 재생성)
- DELETE: 판정하지 않는다. "테마 레지스트리에서 제거됨(히스토리 유사 신호) + 이번 실행이
  생성하지 않음(관측 부재)"인 기존 문서만 **deprecated 후보로 표시**한다 — 물리 삭제는
  절대 하지 않는다 (decision-manual-delete-grace: 표시 -> 유예 -> 사람 확인(MR) 후 삭제).
"""
from __future__ import annotations

from pathlib import Path

from .themes import MANUAL_THEMES

_DEPRECATED_MARK = "status: deprecated-candidate"
_DEPRECATED_TAG = (
    f"{_DEPRECATED_MARK}\n"
    "deprecated_reason: 이번 순회에서 관측 근거 없음(단일 신호) — "
    "커밋 히스토리 교차 확인과 MR 사람 확인 전까지 유예"
)


def judge_action(out_dir: Path, theme_key: str) -> str:
    """이번 생성이 ADD인지 UPDATE인지 (기존 문서 파일 기준)."""
    return "update" if (out_dir / f"{theme_key}.md").exists() else "add"


def mark_deprecated_candidates(out_dir: Path, generated: list[str]) -> list[str]:
    """레지스트리에 없고 이번 실행도 생성하지 않은 기존 매뉴얼을 deprecated 후보로 표시.

    등록된 테마인데 이번 실행 대상이 아니었던 문서(--themes 부분 실행)는 건드리지
    않는다 — 관측하지 않았을 뿐 제거 신호가 아니다.
    """
    keep = set(MANUAL_THEMES) | set(generated)
    marked: list[str] = []
    for p in sorted(out_dir.glob("*.md")):
        if p.stem in keep:
            continue
        text = p.read_text(encoding="utf-8")
        if _DEPRECATED_MARK in text[:600]:
            continue   # 이미 표시됨 (유예 중) — 멱등
        if text.startswith("---"):
            text = text.replace("---", f"---\n{_DEPRECATED_TAG}", 1)
        else:
            text = f"---\n{_DEPRECATED_TAG}\n---\n\n{text}"
        p.write_text(text, encoding="utf-8")
        marked.append(p.stem)
    return marked
