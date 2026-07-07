"""write -> critic -> 재시도 루프 (diff/init 러너 공용).

원본 재시도 정책 이식: critic fail 시 최대 2회 재작성, 초과 시 경고 태그 삽입 후 저장.
개선: critic이 grounding(소스 대조)까지 검증하고, 피드백을 다음 write에 주입해 핀포인트 수정.
"""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage

from ..common import events as ev
from ..common.run import run_graph
from .graph import build_critic_graph
from .mermaid_lint import lint_mermaid
from .output import strip_reasoning

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_MAX_RETRY = 2   # 원본 Hard Cap


def _extract_json_obj(text: str, key: str) -> dict:
    """응답에서 주어진 key를 포함하는 JSON 오브젝트 추출 (<think>·펜스 대비)."""
    body = _THINK_RE.sub("", text)
    idx = body.find(f'"{key}"')
    if idx == -1:
        return {}
    start = body.rfind("{", 0, idx)
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(body)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(body[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def _run_writer(writer_graph_factory, base_prompt, feedback, observer):
    """writer 그래프 1회 실행 -> 문서 마크다운(<think> 제거) 반환."""
    prompt = base_prompt
    if feedback:
        fb = "\n".join(f"  - {f}" for f in feedback)
        prompt += f"\n\n## critic 피드백 (지적된 부분만 핀포인트 수정, 전면 재작성 금지)\n{fb}"
    graph = writer_graph_factory()
    final = run_graph(
        graph,
        {"messages": [HumanMessage(content=prompt)],
         "theme": "", "changed_files": [], "from_sha": "", "to_sha": ""},
        observer, config={"recursion_limit": 25},
    )
    last = final["messages"][-1]
    text = last.content if isinstance(last.content, str) else str(last.content)
    return strip_reasoning(text)


def _run_critic(model, client, theme, doc_md, source_files, ref, run_id, stage, observer):
    graph = build_critic_graph(
        model=model, client=client, theme=theme, doc_markdown=doc_md,
        source_files_read=source_files, ref=ref, run_id=run_id, stage=stage,
    )
    final = run_graph(
        graph,
        {"messages": [HumanMessage(content="이 문서를 3단계로 검증하고 JSON으로만 판정하라.")],
         "theme": "", "changed_files": [], "from_sha": "", "to_sha": ""},
        observer, config={"recursion_limit": 20},
    )
    last = final["messages"][-1]
    text = last.content if isinstance(last.content, str) else str(last.content)
    verdict = _extract_json_obj(text, "result")
    return verdict or {"result": "unknown"}


def _extract_source_files(doc_md: str) -> list[str]:
    """문서 frontmatter의 source_files 목록 추출 (critic grounding 대상)."""
    m = re.search(r"source_files:\s*\[([^\]]*)\]", doc_md)
    if not m:
        return []
    return [s.strip().strip('"\'') for s in m.group(1).split(",") if s.strip()]


def generate_with_critic(
    *, model, client, theme, ref, run_id, stage, writer_graph_factory,
    base_prompt, observer, emit_ctx,
):
    """write -> critic -> 재시도. (문서 마크다운, 최종 verdict, warned) 반환.

    emit_ctx(layer, stage, status, detail): 러너의 이벤트 방출 콜백.
    """
    feedback: list[str] = []
    doc_md = ""
    verdict = {"result": "unknown"}
    warned = False

    for attempt in range(_MAX_RETRY + 1):
        emit_ctx("engine_call", stage, "running",
                 {"phase": "write", "attempt": attempt + 1})
        doc_md = _run_writer(writer_graph_factory, base_prompt, feedback, observer)

        # 1) mermaid lint (결정적 코드 검증) — 빠르고 확실하니 먼저.
        mermaid_errs = lint_mermaid(doc_md)
        emit_ctx("engine_call", stage, "running",
                 {"phase": "mermaid-lint",
                  "verdict": "pass" if not mermaid_errs else "fail",
                  "errors": mermaid_errs[:3], "attempt": attempt + 1})

        # 2) LLM critic (frontmatter + 테마 적합성 + grounding)
        src = _extract_source_files(doc_md)
        emit_ctx("engine_call", stage, "running", {"phase": "critic", "attempt": attempt + 1})
        verdict = _run_critic(model, client, theme, doc_md, src, ref, run_id,
                              f"critic:{stage}", observer)

        critic_pass = verdict.get("result") == "pass"
        if critic_pass and not mermaid_errs:
            emit_ctx("engine_call", stage, "running",
                     {"phase": "verify", "verdict": "pass", "attempt": attempt + 1})
            return doc_md, verdict, False

        # 실패 사유 합치기: critic 피드백 + mermaid lint 오류 -> writer 핀포인트 수정
        feedback = list(verdict.get("feedback", []) or [])
        if mermaid_errs:
            feedback = [f"[mermaid] {e}" for e in mermaid_errs] + feedback
        if not feedback:
            feedback = ["검증 실패 (사유 미상)"]
        verdict["mermaid_errors"] = mermaid_errs
        emit_ctx("engine_call", stage, "running",
                 {"phase": "verify", "verdict": "fail",
                  "feedback": feedback[:3], "attempt": attempt + 1})

    # Hard Cap 초과 — 경고 태그 삽입 후 저장 (원본 정책)
    warned = True
    warn_tag = "auto_generated_warning: 검증 미통과 - 수동 검토 필요"
    if doc_md.startswith("---"):
        doc_md = doc_md.replace("---", f"---\n{warn_tag}", 1)
    else:
        doc_md = f"---\n{warn_tag}\n---\n\n{doc_md}"
    return doc_md, verdict, warned
