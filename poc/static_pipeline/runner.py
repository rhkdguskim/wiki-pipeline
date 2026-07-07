"""정적 파이프라인 결정적 오케스트레이션.

compare -> 테마 매핑 -> 테마당 1회 에이전트 그래프 invoke -> 저장.
compare·매핑·저장·MR은 전부 일반 코드. 에이전트는 '테마 문서 생성' 판단만 한다.
"""
from __future__ import annotations

import uuid

from langchain_core.messages import HumanMessage

from ..common import events as ev
from ..common.config import Settings
from ..common.llm import build_chat_model
from ..common.observer import Observer
from ..common.run import run_graph
from .gitlab_client import GitLabClient
from .graph import build_static_graph
from .output import save_theme_doc, submit_mr_stub
from .theme_mapping import filter_source_files, themes_for_changes


def run_static(settings: Settings, from_sha: str, to_sha: str) -> dict:
    run_id = "static-" + uuid.uuid4().hex[:8]
    observer = Observer(run_id, settings.out_path)
    client = GitLabClient(settings)
    model = build_chat_model(settings)
    summary: dict = {"run_id": run_id, "themes": {}, "changed": 0, "sources": 0}

    def rev(layer, stage, status="running", progress=None, detail=None):
        observer.sink(ev.make_event(
            pipeline_id="static", run_id=run_id, layer=layer,
            stage=stage, status=status, progress=progress, detail=detail,
        ))

    try:
        rev("run", "static-pipeline", "running",
            detail={"from": from_sha[:10], "to": to_sha[:10]})

        # 1) compare (stage)
        rev("stage", "compare", "running")
        diffs = client.compare(from_sha, to_sha)
        changed = [d.get("new_path") for d in diffs if d.get("new_path")]
        sources = filter_source_files(changed)
        summary["changed"] = len(changed)
        summary["sources"] = len(sources)
        rev("stage", "compare", "done",
            detail={"changed": len(changed), "sources": len(sources)})

        if not sources:
            rev("run", "static-pipeline", "done", detail={"note": "문서화할 소스 변경 없음"})
            return summary

        # 2) 테마 매핑 (결정적)
        theme_map = themes_for_changes(changed, settings.theme_list)
        rev("stage", "theme-mapping", "done",
            detail={"themes": list(theme_map.keys())})

        # 3) 테마당 1회 에이전트 루프 (engine_call)
        themes = list(theme_map.keys())
        for i, theme in enumerate(themes, 1):
            files = theme_map[theme]
            rev("engine_call", f"theme:{theme}", "running",
                progress={"n": i, "m": len(themes), "unit": "theme"})
            graph = build_static_graph(
                model=model, client=client, theme=theme,
                changed_files=files, from_sha=from_sha, to_sha=to_sha,
                run_id=run_id,
            )
            prompt = (
                f"'{theme}' 테마의 기술문서를 작성하라. 변경 파일 {len(files)}개는 "
                f"시스템 프롬프트에 있다. 필요하면 도구로 코드를 읽고, 완성되면 frontmatter "
                f"포함 마크다운만 출력하라."
            )
            final = run_graph(
                graph,
                {"messages": [HumanMessage(content=prompt)],
                 "theme": theme, "changed_files": files,
                 "from_sha": from_sha, "to_sha": to_sha},
                observer,
                config={"recursion_limit": 25},
            )
            last = final["messages"][-1]
            content = last.content if isinstance(last.content, str) else str(last.content)
            path = save_theme_doc(settings.out_path, theme, content)
            mr = submit_mr_stub(theme, path, settings.docshub_mr_enabled)
            summary["themes"][theme] = {"file": str(path), "chars": path.stat().st_size}
            rev("engine_call", f"theme:{theme}", "done",
                progress={"n": i, "m": len(themes), "unit": "theme"},
                detail={"saved": path.name, "mr": mr})

        rev("run", "static-pipeline", "done",
            detail={"generated": list(summary["themes"].keys())})
        return summary
    except Exception as e:  # noqa: BLE001
        rev("run", "static-pipeline", "failed",
            detail={"error": f"{type(e).__name__}: {e}"})
        raise
    finally:
        client.close()
        observer.close()
