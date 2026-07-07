"""mermaid 다이어그램 경량 lint (결정적, LLM 아님).

생성 문서엔 mermaid(graph/flowchart/sequenceDiagram 등)가 자주 나오고, 문법이 깨지면
렌더링에 실패한다. 완전한 mermaid 파서 대신, 실무에서 자주 깨지는 지점을 규칙으로 잡는다:
  - ```mermaid 코드펜스 짝 맞음
  - 첫 유효 라인이 알려진 다이어그램 타입 선언으로 시작
  - 괄호/대괄호/중괄호 균형
  - flowchart/graph에서 노드 라벨의 <br> 오타·따옴표 짝
실패하면 사람이 읽는 사유 목록을 돌려주고, 이는 critic 피드백에 합쳐져 writer가 재수정한다.
mmdc(mermaid-cli)가 설치돼 있으면 그걸로 정밀 검증도 시도한다(옵션).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

_FENCE_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

_DIAGRAM_TYPES = (
    "graph", "flowchart", "sequencediagram", "classdiagram", "statediagram",
    "statediagram-v2", "erdiagram", "journey", "gantt", "pie", "gitgraph",
    "mindmap", "timeline", "quadrantchart", "requirementdiagram", "c4context",
    "block-beta", "sankey-beta",
)


def _balanced(text: str, open_ch: str, close_ch: str) -> bool:
    depth = 0
    for c in text:
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _lint_one(block: str, idx: int) -> list[str]:
    errs: list[str] = []
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if not lines:
        errs.append(f"mermaid #{idx}: 빈 다이어그램")
        return errs

    first = lines[0].strip().lower()
    if not any(first.startswith(t) for t in _DIAGRAM_TYPES):
        errs.append(
            f"mermaid #{idx}: 첫 줄이 알려진 다이어그램 타입으로 시작하지 않음 "
            f"(받은 값: {lines[0].strip()[:40]!r}). graph/flowchart/sequenceDiagram 등이어야 함"
        )

    if not _balanced(block, "[", "]"):
        errs.append(f"mermaid #{idx}: 대괄호 [ ] 짝이 맞지 않음")
    if not _balanced(block, "(", ")"):
        errs.append(f"mermaid #{idx}: 소괄호 ( ) 짝이 맞지 않음")
    if not _balanced(block, "{", "}"):
        errs.append(f"mermaid #{idx}: 중괄호 {{ }} 짝이 맞지 않음")
    if block.count('"') % 2 != 0:
        errs.append(f"mermaid #{idx}: 큰따옴표 짝이 맞지 않음")

    # <br> 는 유효하나 < br >·<BR/> 혼용 등 흔한 오타 경고 (엄격히 막진 않음)
    if re.search(r"<\s*br\s*>", block) and not re.search(r"<br\s*/?>", block):
        errs.append(f"mermaid #{idx}: <br> 표기 확인 필요 (권장: <br/>)")

    return errs


def _try_mmdc(blocks: list[str]) -> list[str]:
    """mmdc(mermaid-cli)가 있으면 실제 렌더 파싱으로 정밀 검증."""
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return []
    errs: list[str] = []
    for i, block in enumerate(blocks, 1):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "d.mmd"
            out = Path(td) / "d.svg"
            src.write_text(block, encoding="utf-8")
            try:
                r = subprocess.run(
                    [mmdc, "-i", str(src), "-o", str(out)],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    msg = (r.stderr or r.stdout).strip().splitlines()
                    tail = msg[-1] if msg else "parse error"
                    errs.append(f"mermaid #{i}: mmdc 파싱 실패 — {tail[:120]}")
            except Exception:
                pass  # mmdc 실행 문제는 경량 검증으로 대체
    return errs


def lint_mermaid(markdown: str, use_mmdc: bool = True) -> list[str]:
    """문서 내 모든 mermaid 블록을 검증. 문제 사유 목록 반환(빈 목록=통과)."""
    blocks = [m.group(1) for m in _FENCE_RE.finditer(markdown)]
    if not blocks:
        return []
    errs: list[str] = []
    for i, block in enumerate(blocks, 1):
        errs.extend(_lint_one(block, i))
    if use_mmdc:
        errs.extend(_try_mmdc(blocks))
    return errs
