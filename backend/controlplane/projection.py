"""이벤트 -> KPI 프로젝션 (파일/DB 공용) + 레거시 events JSONL 파일 리더.

summarize_events는 이벤트 dict 리스트만 받으므로 출처(webhook 적재 DB or
러너 로컬 JSONL)와 무관하게 동일한 요약을 만든다 (concept-observability-contract).
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

_MAX_CHUNK = 4 * 1024 * 1024
_MAX_SUMMARY_BYTES = 32 * 1024 * 1024


def _parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def summarize_events(events: list[dict], *, run_id: str, source_id: str = "",
                     path: str = "", artifacts: list[dict] | None = None) -> dict:
    stages: dict[str, dict] = {}
    usage = {"input_tokens": 0, "output_tokens": 0, "llm_calls": 0}
    usage_by_model: dict[str, dict] = {}
    tools: Counter = Counter()
    pipeline = ""
    run_status = ""
    first_ts = None
    last_ts = None
    errors: list[dict] = []
    warnings: list[dict] = []
    generated: list[dict] = []
    timeline: list[dict] = []

    for e in events:
        ts = _parse_ts(e.get("ts"))
        if ts is not None:
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
        pipeline = e.get("pipeline_id") or pipeline
        detail = e.get("detail") or {}
        layer = e.get("layer")
        stage_name = e.get("stage") or ""
        status = e.get("status") or ""

        if layer == "run":
            run_status = status or run_status

        if layer in ("stage", "engine_call"):
            st = stages.setdefault(stage_name, {
                "name": stage_name, "layer": layer, "status": status,
                "first_ts": e.get("ts"), "last_ts": e.get("ts"),
                "input_tokens": 0, "output_tokens": 0, "tools": 0,
            })
            st["status"] = status or st["status"]
            st["last_ts"] = e.get("ts") or st["last_ts"]
            st["progress"] = e.get("progress") or st.get("progress") or {}
            if status == "failed":
                errors.append({"stage": stage_name, "kind": "stage_failed",
                               "message": detail.get("error", "stage failed")})
            saved = detail.get("saved") or detail.get("file")
            if saved:
                generated.append({
                    "stage": stage_name, "path": saved,
                    "verdict": detail.get("verdict", ""),
                    "warned": bool(detail.get("warned")),
                    "kept": bool(detail.get("kept")),
                })
                if detail.get("warned"):
                    warnings.append({"stage": stage_name, "message": "critic warning tag applied"})

        if layer == "agent_step":
            st = stages.setdefault(stage_name, {
                "name": stage_name, "layer": "agent_step", "status": "",
                "first_ts": e.get("ts"), "last_ts": e.get("ts"),
                "input_tokens": 0, "output_tokens": 0, "tools": 0,
            })
            st["last_ts"] = e.get("ts") or st["last_ts"]
            kind = detail.get("kind")
            if kind == "usage":
                input_tokens = int(detail.get("input_tokens") or 0)
                output_tokens = int(detail.get("output_tokens") or 0)
                usage["input_tokens"] += input_tokens
                usage["output_tokens"] += output_tokens
                usage["llm_calls"] += 1
                st["input_tokens"] += input_tokens
                st["output_tokens"] += output_tokens
                provider = str(detail.get("provider") or detail.get("vendor") or "unknown")
                model = str(detail.get("model") or detail.get("model_name") or "unknown")
                model_key = f"{provider}::{model}"
                model_usage = usage_by_model.setdefault(model_key, {
                    "provider": provider, "model": model,
                    "input_tokens": 0, "output_tokens": 0, "calls": 0,
                })
                model_usage["input_tokens"] += input_tokens
                model_usage["output_tokens"] += output_tokens
                model_usage["calls"] += 1
            elif kind == "tool_use":
                tools[str(detail.get("tool") or "tool")] += 1
                st["tools"] += 1
            elif kind == "tool_result" and not detail.get("ok", True):
                errors.append({"stage": stage_name, "kind": "tool_result",
                               "message": detail.get("preview", "")})
            elif kind == "llm_retry":
                warnings.append({"stage": stage_name, "kind": "llm_retry",
                                 "message": detail.get("error", "")})

        if layer in ("run", "stage", "engine_call") or (detail.get("kind") in ("tool_use", "tool_result", "llm_retry")):
            timeline.append({"ts": e.get("ts"), "layer": layer, "stage": stage_name,
                             "status": status, "detail": detail})

    stage_rows = sorted(stages.values(), key=lambda s: s.get("first_ts") or "")
    done = sum(1 for s in stage_rows if s.get("status") == "done")
    failed = sum(1 for s in stage_rows if s.get("status") == "failed")
    current = next((s["name"] for s in reversed(stage_rows) if s.get("status") == "running"),
                   stage_rows[-1]["name"] if stage_rows else "")
    tool_calls = sum(tools.values())
    tool_errors = sum(1 for e in errors if e.get("kind") == "tool_result")
    staged_total = len([s for s in stage_rows if s.get("status")])
    duration = round(last_ts - first_ts, 3) if first_ts is not None and last_ts is not None else None
    return {
        "run_id": run_id,
        "source_id": source_id,
        "path": path,
        "pipeline_id": pipeline,
        "status": run_status or ("failed" if failed else "running"),
        "current_stage": current,
        "started_at": datetime.fromtimestamp(first_ts).isoformat() if first_ts else "",
        "last_event_at": datetime.fromtimestamp(last_ts).isoformat() if last_ts else "",
        "duration_sec": duration,
        "event_count": len(events),
        "kpi": {
            "stage_done": done,
            "stage_total": staged_total,
            "stage_failed": failed,
            "completion_pct": round(done / staged_total * 100, 1) if staged_total else 0,
            "token_total": usage["input_tokens"] + usage["output_tokens"],
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "llm_calls": usage["llm_calls"],
            "tool_calls": tool_calls,
            "tool_errors": tool_errors,
            "tool_reliability_pct": round((tool_calls - tool_errors) / tool_calls * 100, 1)
                                    if tool_calls else 100,
            "warnings": len(warnings),
            "errors": len(errors),
        },
        "stages": stage_rows,
        "tools": [{"name": name, "calls": count} for name, count in tools.most_common()],
        "usage_by_model": list(usage_by_model.values()),
        "errors": errors[-20:],
        "warnings": warnings[-20:],
        "generated": generated[-50:],
        "artifacts": artifacts or [],
        "timeline": timeline[-80:],
    }


# ── 레거시 JSONL 파일 리더 (러너 로컬 감사 사본 / CLI 단독 실행 조회) ──

def run_id_from_path(path: Path) -> str:
    return path.name[len("events-"):-len(".jsonl")]


def source_from_path(out_dir: Path, path: Path) -> str:
    try:
        rel = path.parent.relative_to(out_dir)
    except ValueError:
        return ""
    return "" if str(rel) == "." else rel.parts[0]


def find_run_path(out_dir: Path, run_id: str) -> Path | None:
    for p in out_dir.rglob(f"events-{run_id}.jsonl"):
        if p.is_file() and run_id_from_path(p) == run_id:
            return p
    return None


def list_file_runs(out_dir: Path) -> list[dict]:
    runs = []
    for p in out_dir.rglob("events-*.jsonl"):
        st = p.stat()
        runs.append({
            "run_id": run_id_from_path(p),
            "source_id": source_from_path(out_dir, p),
            "path": str(p.relative_to(out_dir)),
            "size": st.st_size,
            "age_sec": round(time.time() - st.st_mtime, 1),
        })
    runs.sort(key=lambda r: r["age_sec"])
    return runs


def read_new_file_events(path: Path, offset: int) -> dict:
    """offset 이후의 완결 라인만 파싱 — 부분 라인(쓰는 중)은 다음 폴링으로."""
    size = path.stat().st_size
    if offset < 0 or offset > size:
        offset = 0
    events: list[dict] = []
    new_offset = offset
    if size > offset:
        with path.open("rb") as f:
            f.seek(offset)
            buf = f.read(_MAX_CHUNK)
        nl = buf.rfind(b"\n")
        if nl >= 0:
            for ln in buf[: nl + 1].decode("utf-8", "replace").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    events.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
            new_offset = offset + nl + 1
    return {"events": events, "offset": new_offset, "size": size,
            "age_sec": round(time.time() - path.stat().st_mtime, 1)}


def read_all_file_events(path: Path) -> list[dict]:
    size = path.stat().st_size
    start = max(0, size - _MAX_SUMMARY_BYTES)
    events: list[dict] = []
    with path.open("rb") as f:
        if start:
            f.seek(start)
            f.readline()
        for raw in f:
            try:
                events.append(json.loads(raw.decode("utf-8", "replace")))
            except json.JSONDecodeError:
                continue
    return events


def list_artifacts(run_path: Path, out_dir: Path) -> list[dict]:
    root = run_path.parent
    artifacts = []
    for p in root.rglob("*.md"):
        if not p.is_file():
            continue
        try:
            st = p.stat()
            artifacts.append({"path": str(p.relative_to(out_dir)), "name": p.name,
                              "size": st.st_size, "mtime": st.st_mtime})
        except OSError:
            continue
    artifacts.sort(key=lambda a: a["mtime"], reverse=True)
    return artifacts[:100]
