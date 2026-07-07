"""정적 파이프라인 diff 러너 (증분).

결정적 오케스트레이션: compare -> 테마 매핑 -> 테마당 [write -> mermaid-lint + critic -> 재시도] -> 저장.
판단(문서 생성·검증)만 에이전트, 나머지는 일반 코드.
"""
from __future__ import annotations

import uuid

from ..common.config import Settings
from ..common.docshub import submit_mr_stub
from ..common.llm import build_chat_model
from ..common.observer import Observer
from .generate import generate_with_critic
from .gitlab_client import GitLabClient
from .graph import build_diff_writer_graph
from .output import save_theme_doc
from .pipeline_state import save_state
from .themes import DEFAULT_THEMES
from .theme_mapping import filter_source_files, themes_for_changes


def run_static(settings: Settings, from_sha: str, to_sha: str | None,
               themes: list[str] | None = None) -> dict:
    run_id = "static-" + uuid.uuid4().hex[:8]
    observer = Observer(run_id, settings.out_path)
    client = GitLabClient(settings)
    model = build_chat_model(settings)
    themes = themes or DEFAULT_THEMES
    summary: dict = {"run_id": run_id, "themes": {}, "changed": 0, "sources": 0, "warned": []}

    rev = observer.emitter("static", run_id)

    try:
        # to_sha 미지정(상태 기반 증분)이면 default branch HEAD로 해석.
        if not to_sha or to_sha.upper() == "HEAD":
            to_sha = client.resolve_ref(client.default_branch())
        rev("run", "static-diff", "running", detail={"from": from_sha[:10], "to": to_sha[:10]})

        rev("stage", "compare", "running")
        diffs = client.compare(from_sha, to_sha)
        changed = [d.get("new_path") for d in diffs if d.get("new_path")]
        sources = filter_source_files(changed)
        summary["changed"] = len(changed)
        summary["sources"] = len(sources)
        rev("stage", "compare", "done", detail={"changed": len(changed), "sources": len(sources)})

        if not sources:
            # 변경 없음도 성공 — "여기까지 봤다"로 sha 전진 (재실행 시 같은 구간 재검사 방지).
            _advance(settings, client, to_sha, summary, rev)
            rev("run", "static-diff", "done", detail={"note": "문서화할 소스 변경 없음"})
            return summary

        theme_map = themes_for_changes(changed, themes)
        rev("stage", "theme-mapping", "done", detail={"themes": list(theme_map.keys())})

        theme_ids = list(theme_map.keys())
        for i, theme in enumerate(theme_ids, 1):
            files = theme_map[theme]
            stage = f"theme:{theme}"
            rev("engine_call", stage, "running",
                progress={"n": i, "m": len(theme_ids), "unit": "theme"})

            def factory(_t=theme, _f=files, no_tools=False):
                return build_diff_writer_graph(
                    model=model, client=client, theme=_t, changed_files=_f,
                    from_sha=from_sha, to_sha=to_sha, run_id=run_id,
                    no_tools=no_tools,
                )

            base_prompt = (
                f"'{theme}' 테마의 기술문서를 작성하라. 변경 파일과 테마 정의는 시스템 "
                f"프롬프트에 있다. 완성되면 frontmatter 포함 마크다운만 출력하라."
            )
            doc_md, verdict, warned = generate_with_critic(
                model=model, client=client, theme=theme, ref=to_sha, run_id=run_id,
                stage=stage, writer_graph_factory=factory, base_prompt=base_prompt,
                observer=observer, emit_ctx=rev,
            )
            path = save_theme_doc(settings.out_path, theme, doc_md)
            mr = submit_mr_stub(theme, path, settings.docshub_mr_enabled)
            summary["themes"][theme] = {
                "file": str(path), "chars": path.stat().st_size,
                "verdict": verdict.get("result"), "warned": warned,
            }
            if warned:
                summary["warned"].append(theme)
            rev("engine_call", stage, "done",
                progress={"n": i, "m": len(theme_ids), "unit": "theme"},
                detail={"saved": path.name, "verdict": verdict.get("result"),
                        "warned": warned, "mr": mr})

        # 상태 전진 — 성공 후에만 (concept-idempotent-sha). 실패 시 상태 불변.
        _advance(settings, client, to_sha, summary, rev)
        rev("run", "static-diff", "done",
            detail={"generated": list(summary["themes"].keys()), "warned": summary["warned"]})
        return summary
    except Exception as e:  # noqa: BLE001
        rev("run", "static-diff", "failed", detail={"error": f"{type(e).__name__}: {e}"})
        raise
    finally:
        client.close()
        observer.close()


def _advance(settings, client, to_sha: str, summary: dict, rev) -> None:
    """last_processed_sha 전진 (성공 경로에서만 호출)."""
    try:
        full = to_sha if len(to_sha) == 40 else client.resolve_ref(to_sha)
        sp = save_state(
            settings.out_path, project_id=settings.gitlab_project_id,
            last_processed_sha=full, ref=to_sha, op="diff",
            extra={"themes": list(summary["themes"].keys())},
        )
        summary["last_processed_sha"] = full
        rev("stage", "state-advance", "done",
            detail={"last_processed_sha": full[:12], "file": sp.name})
    except Exception as e:  # noqa: BLE001
        rev("stage", "state-advance", "failed",
            detail={"error": f"{type(e).__name__}: {e}"})
