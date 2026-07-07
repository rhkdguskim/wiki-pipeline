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


def _mmdc_reason(output: str) -> str:
    """mmdc stderr에서 사람이 고칠 수 있는 파싱 오류 문맥을 추출.

    스택트레이스 마지막 줄 대신 'Parse error on line N: ... Expecting ...' 블록을 찾는다 —
    writer가 피드백으로 받았을 때 어느 줄을 어떻게 고칠지 알 수 있어야 한다.
    """
    lines = output.strip().splitlines()
    for i, ln in enumerate(lines):
        low = ln.strip()
        if "Parse error" in low or "Expecting" in low or "Syntax error" in low:
            return " | ".join(x.strip() for x in lines[i:i + 4] if x.strip())[:300]
    for ln in lines:
        if "Error" in ln and "node_modules" not in ln:
            return ln.strip()[:200]
    return (lines[0].strip()[:150] if lines else "parse error")


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
                    errs.append(f"mermaid #{i}: mmdc 파싱 실패 — {_mmdc_reason(r.stderr or r.stdout)}")
            except Exception:
                pass  # mmdc 실행 문제는 경량 검증으로 대체
    return errs


# ── 결정적 정규화 (lint 이전 단계) ──
# 엣지 라벨(-->|...|)은 mermaid 문법의 취약 지점 — HTML 태그(<br/>)와 괄호가
# 파서를 깨뜨린다. init 실측에서 writer가 lint 피드백을 3회 받고도 같은 지점에서
# 반복 실패했다 — 재시도로 고칠 게 아니라 코드로 고친다. 노드 라벨(["..."])은
# <br/>·괄호가 유효하므로 건드리지 않는다.
_EDGE_LABEL_RE = re.compile(r"([<>ox]?(?:-{2,}|={2,}|-\.+-)[>ox]?\s*\|)([^|\n]+)(\|)")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LABEL_SPECIALS = set('()[]{}<>')


def _fix_edge_label(m: re.Match) -> str:
    label = _BR_RE.sub(" ", m.group(2))
    label = re.sub(r"\s+", " ", label).strip()
    core = label.strip('"').strip()
    if any(c in core for c in _LABEL_SPECIALS):
        label = '"' + core.replace('"', "'") + '"'
    return f"{m.group(1)}{label}{m.group(3)}"


def sanitize_mermaid(markdown: str) -> str:
    """flowchart/graph 블록의 엣지 라벨을 파서 안전 형태로 정규화 (그 외 블록 불변)."""
    def _fix(m: re.Match) -> str:
        block = m.group(1)
        first = next((ln for ln in block.splitlines() if ln.strip()), "").strip().lower()
        if not first.startswith(("graph", "flowchart")):
            return m.group(0)
        return m.group(0).replace(block, _EDGE_LABEL_RE.sub(_fix_edge_label, block), 1)
    return _FENCE_RE.sub(_fix, markdown)


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
