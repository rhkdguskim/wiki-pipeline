"""docs-hub 제출 — 두 파이프라인이 공유하는 MR 게이트 (decision-mr-review-gate).

관리 서버·docs-hub·MR 게이트는 두 파이프라인의 유일한 공유 접점이다
(decision-manual-pipeline-separate) — 그래서 이 모듈만 common에 있다.
PoC는 스텁: DOCSHUB_MR_ENABLED=true면 실제 MR API 연결 지점.
"""
from __future__ import annotations

from pathlib import Path


def submit_mr_stub(name: str, path: Path, enabled: bool) -> str:
    if enabled:
        return f"[MR 제출 훅] {name}: 실제 MR API 연결 지점 (미구현)"
    return f"[MR 스텁] {name} -> {path.name} (DOCSHUB_MR_ENABLED=false, 로컬 저장만)"
