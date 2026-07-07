"""관측 대시보드 API 서버 — 표준 라이브러리만으로 events JSONL을 증분/요약 서빙.

    python -m backend.dashboard.serve            # http://127.0.0.1:8420
    python -m backend.dashboard.serve --port 9000 --out D:/path/to/out

API (모두 GET, JSON):
- /            : API 엔드포인트 목록
- /api/runs    : out/events-*.jsonl 목록 [{run_id, size, age_sec}] (최신순)
- /api/sources : .env/SCM_SOURCES_JSON 기반 source 목록 + 상태 포인터
- /api/overview: 최근 run projection 집계
- /api/run-summary?run=<id>
               : run 1건의 KPI·stage·tool·error·artifact projection
- /api/events?run=<id>&offset=<bytes>
               : offset 이후의 완결 라인만 파싱해 반환 {events, offset, size, age_sec}
                 offset 프로토콜이라 파일이 커져도 폴링 비용은 증분뿐이다.

파이프라인 프로세스와 완전 분리 — observer가 flush하는 파일을 읽기만 하므로
실행 중인 run이든 끝난 run이든 같은 경로로 본다. 쓰기 API는 없다.
프런트엔드는 Vite/별도 웹 서버가 담당하고, 이 서버는 정적 파일을 서빙하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..common.docshub import build_mr_plan, submit_gitlab_mr
from .store import ControlStore, default_db_path

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_CHUNK = 4 * 1024 * 1024   # 폴링 1회 최대 읽기 (초기 따라잡기는 클라이언트가 반복 호출)
_MAX_SUMMARY_BYTES = 32 * 1024 * 1024


def read_new_events(path: Path, offset: int) -> dict:
    """offset 이후의 완결 라인만 파싱. 부분 라인(쓰는 중)은 다음 폴링으로 미룬다."""
    size = path.stat().st_size
    if offset < 0 or offset > size:
        offset = 0   # 파일 교체/절단 방어 — 처음부터 다시
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
                    pass   # 손상 라인은 건너뛴다 (감사 원본은 그대로 남는다)
            new_offset = offset + nl + 1
    return {
        "events": events,
        "offset": new_offset,
        "size": size,
        "age_sec": round(time.time() - path.stat().st_mtime, 1),
    }


def _parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read_all_events(path: Path) -> list[dict]:
    """대시보드 projection용 전체 읽기. 너무 큰 파일은 끝부분만 읽어 서버를 보호한다."""
    size = path.stat().st_size
    start = max(0, size - _MAX_SUMMARY_BYTES)
    events: list[dict] = []
    with path.open("rb") as f:
        if start:
            f.seek(start)
            f.readline()   # 중간 라인 절단 방지
        for raw in f:
            try:
                events.append(json.loads(raw.decode("utf-8", "replace")))
            except json.JSONDecodeError:
                continue
    return events


def _run_id_from_path(path: Path) -> str:
    return path.name[len("events-"):-len(".jsonl")]


def _source_from_path(out_dir: Path, path: Path) -> str:
    try:
        rel = path.parent.relative_to(out_dir)
    except ValueError:
        return ""
    return "" if str(rel) == "." else rel.parts[0]


def find_run_path(out_dir: Path, run_id: str) -> Path | None:
    for p in out_dir.rglob(f"events-{run_id}.jsonl"):
        if p.is_file() and _run_id_from_path(p) == run_id:
            return p
    return None


def list_runs(out_dir: Path) -> list[dict]:
    runs = []
    for p in out_dir.rglob("events-*.jsonl"):
        run_id = _run_id_from_path(p)
        st = p.stat()
        runs.append({
            "run_id": run_id,
            "source_id": _source_from_path(out_dir, p),
            "path": str(p.relative_to(out_dir)),
            "size": st.st_size,
            "age_sec": round(time.time() - st.st_mtime, 1),
        })
    runs.sort(key=lambda r: r["age_sec"])
    return runs


def list_artifacts(run_path: Path, out_dir: Path) -> list[dict]:
    """run이 속한 source/output 폴더의 Markdown 산출물을 보여준다."""
    root = run_path.parent
    artifacts = []
    for p in root.rglob("*.md"):
        if not p.is_file():
            continue
        try:
            st = p.stat()
            artifacts.append({
                "path": str(p.relative_to(out_dir)),
                "name": p.name,
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
        except OSError:
            continue
    artifacts.sort(key=lambda a: a["mtime"], reverse=True)
    return artifacts[:100]


def summarize_events(events: list[dict], *, run_path: Path, out_dir: Path) -> dict:
    stages: dict[str, dict] = {}
    usage = {"input_tokens": 0, "output_tokens": 0, "llm_calls": 0}
    tools = Counter()
    pipeline = ""
    run_status = ""
    first_ts = None
    last_ts = None
    errors = []
    warnings = []
    generated = []
    timeline = []

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
                    "stage": stage_name,
                    "path": saved,
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
                usage["input_tokens"] += int(detail.get("input_tokens") or 0)
                usage["output_tokens"] += int(detail.get("output_tokens") or 0)
                usage["llm_calls"] += 1
                st["input_tokens"] += int(detail.get("input_tokens") or 0)
                st["output_tokens"] += int(detail.get("output_tokens") or 0)
            elif kind == "tool_use":
                tool = str(detail.get("tool") or "tool")
                tools[tool] += 1
                st["tools"] += 1
            elif kind == "tool_result" and not detail.get("ok", True):
                errors.append({"stage": stage_name, "kind": "tool_result",
                               "message": detail.get("preview", "")})
            elif kind == "llm_retry":
                warnings.append({"stage": stage_name, "kind": "llm_retry",
                                 "message": detail.get("error", "")})

        if layer in ("run", "stage", "engine_call") or (detail.get("kind") in ("tool_use", "tool_result", "llm_retry")):
            timeline.append({
                "ts": e.get("ts"), "layer": layer, "stage": stage_name,
                "status": status, "detail": detail,
            })

    stage_rows = sorted(stages.values(), key=lambda s: s.get("first_ts") or "")
    done = sum(1 for s in stage_rows if s.get("status") == "done")
    failed = sum(1 for s in stage_rows if s.get("status") == "failed")
    current = next((s["name"] for s in reversed(stage_rows) if s.get("status") == "running"),
                   stage_rows[-1]["name"] if stage_rows else "")
    tool_calls = sum(tools.values())
    duration = round(last_ts - first_ts, 3) if first_ts is not None and last_ts is not None else None
    return {
        "run_id": _run_id_from_path(run_path),
        "source_id": _source_from_path(out_dir, run_path),
        "path": str(run_path.relative_to(out_dir)),
        "pipeline_id": pipeline,
        "status": run_status or ("failed" if failed else "running"),
        "current_stage": current,
        "started_at": datetime.fromtimestamp(first_ts).isoformat() if first_ts else "",
        "last_event_at": datetime.fromtimestamp(last_ts).isoformat() if last_ts else "",
        "duration_sec": duration,
        "event_count": len(events),
        "kpi": {
            "stage_done": done,
            "stage_total": len([s for s in stage_rows if s.get("status")]),
            "stage_failed": failed,
            "completion_pct": round((done / len([s for s in stage_rows if s.get("status")]) * 100), 1)
                              if len([s for s in stage_rows if s.get("status")]) else 0,
            "token_total": usage["input_tokens"] + usage["output_tokens"],
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "llm_calls": usage["llm_calls"],
            "tool_calls": tool_calls,
            "tool_errors": sum(1 for e in errors if e.get("kind") == "tool_result"),
            "tool_reliability_pct": round(((tool_calls - sum(1 for e in errors if e.get("kind") == "tool_result")) / tool_calls) * 100, 1)
                                    if tool_calls else 100,
            "warnings": len(warnings),
            "errors": len(errors),
        },
        "stages": stage_rows,
        "tools": [{"name": name, "calls": count} for name, count in tools.most_common()],
        "errors": errors[-20:],
        "warnings": warnings[-20:],
        "generated": generated[-50:],
        "artifacts": list_artifacts(run_path, out_dir),
        "timeline": timeline[-80:],
    }


def run_summary(out_dir: Path, run_id: str) -> dict | None:
    path = find_run_path(out_dir, run_id)
    if not path:
        return None
    return summarize_events(read_all_events(path), run_path=path, out_dir=out_dir)


def docs_hub_mr_plan(out_dir: Path, store: ControlStore, run_id: str, target_id: str = "product-common") -> dict | None:
    summary = run_summary(out_dir, run_id)
    if not summary:
        return None
    target = store.get_doc_target_private(target_id)
    if not target:
        raise ValueError(f"docs-hub target 없음: {target_id}")
    source = store.get_source(summary.get("source_id") or "") if summary.get("source_id") else None
    return build_mr_plan(summary, target=target, source=source, out_dir=out_dir)


def overview(out_dir: Path) -> dict:
    runs = list_runs(out_dir)
    summaries = []
    for run in runs[:20]:
        summary = run_summary(out_dir, run["run_id"])
        if summary:
            summaries.append(summary)
    totals = {
        "runs": len(runs),
        "running": sum(1 for s in summaries if s["status"] == "running"),
        "failed": sum(1 for s in summaries if s["status"] == "failed"),
        "done": sum(1 for s in summaries if s["status"] == "done"),
        "tokens": sum(s["kpi"]["token_total"] for s in summaries),
        "tool_calls": sum(s["kpi"]["tool_calls"] for s in summaries),
        "errors": sum(s["kpi"]["errors"] for s in summaries),
    }
    return {"totals": totals, "recent": summaries}


def enrich_sources(sources: list[dict], out_dir: Path) -> list[dict]:
    from ..static_pipeline.pipeline_state import load_state

    multi = len(sources) > 1
    enriched = []
    for source in sources:
        source_out = out_dir / source["id"] if multi else out_dir
        state = load_state(source_out, source["id"] if multi else None) or {}
        runs = len(list(source_out.rglob("events-*.jsonl"))) if source_out.exists() else 0
        enriched.append({
            **source,
            "out": str(source_out.relative_to(out_dir)) if source_out.is_relative_to(out_dir) else str(source_out),
            "runs": runs,
            "last_processed_sha": state.get("last_processed_sha") or source.get("last_processed_sha", ""),
            "last_op": state.get("last_op", ""),
            "state_updated_at": state.get("updated_at", ""),
        })
    return enriched


def validate_source_payload(payload: dict) -> dict:
    required = ["label", "kind", "url", "project_id"]
    missing = [k for k in required if not str(payload.get(k) or "").strip()]
    warnings = []
    if payload.get("kind", "gitlab") != "gitlab":
        warnings.append("MVP 구현은 GitLab만 실행 지원합니다.")
    if not str(payload.get("dev_branch") or "").strip():
        warnings.append("dev 브랜치가 비어 있으면 개발 문서 배치 대상에서 제외됩니다.")
    if not str(payload.get("release_branch") or "").strip():
        warnings.append("release 브랜치가 비어 있으면 매뉴얼/릴리스 대상에서 제외됩니다.")
    return {"ok": not missing, "missing": missing, "warnings": warnings}


def validate_doc_target_payload(payload: dict) -> dict:
    required = ["label", "kind", "url"]
    missing = [k for k in required if not str(payload.get(k) or "").strip()]
    warnings = []
    if payload.get("kind", "gitlab") != "gitlab":
        warnings.append("MVP 구현은 GitLab MR target만 실행 지원합니다.")
    if not str(payload.get("project_id") or payload.get("project_path") or "").strip():
        warnings.append("GitLab API 호출에는 project_id 또는 project_path가 필요합니다.")
    if not str(payload.get("token") or "").strip():
        warnings.append("토큰이 없으면 MR 생성은 스텁/비활성 모드로만 동작합니다.")
    return {"ok": not missing, "missing": missing, "warnings": warnings}


def make_handler(out_dir: Path, store: ControlStore):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):   # noqa: N802 — 폴링 로그로 콘솔이 잠기는 것 방지
            pass

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON 파싱 실패: {e}") from e
            if not isinstance(data, dict):
                raise ValueError("JSON object가 필요합니다.")
            return data

        def do_OPTIONS(self) -> None:   # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:   # noqa: N802 — http.server 계약
            url = urlparse(self.path)
            try:
                if url.path in ("/", "/api"):
                    self._json({
                        "service": "wiki-pipeline dashboard api",
                        "endpoints": [
                            "/api/runs",
                            "/api/sources",
                            "/api/sources/validate",
                            "/api/docs-hub",
                            "/api/docs-hub/mr-plan?run=<id>&target=product-common",
                            "POST /api/docs-hub/submit-mr",
                            "/api/overview",
                            "/api/run-summary?run=<id>",
                            "/api/events?run=<id>&offset=<bytes>",
                        ],
                    })
                elif url.path == "/api/runs":
                    self._json(list_runs(out_dir))
                elif url.path == "/api/sources":
                    self._json(enrich_sources(store.list_sources(), out_dir))
                elif url.path == "/api/docs-hub":
                    self._json({"targets": store.list_doc_targets()})
                elif url.path == "/api/docs-hub/mr-plan":
                    q = parse_qs(url.query)
                    run = (q.get("run") or [""])[0]
                    target_id = (q.get("target") or ["product-common"])[0]
                    if not _RUN_ID_RE.match(run):
                        self._json({"error": "잘못된 run id"}, 400)
                        return
                    plan = docs_hub_mr_plan(out_dir, store, run, target_id)
                    if not plan:
                        self._json({"error": "run 없음"}, 404)
                        return
                    self._json(plan)
                elif url.path == "/api/overview":
                    self._json(overview(out_dir))
                elif url.path == "/api/run-summary":
                    q = parse_qs(url.query)
                    run = (q.get("run") or [""])[0]
                    if not _RUN_ID_RE.match(run):
                        self._json({"error": "잘못된 run id"}, 400)
                        return
                    summary = run_summary(out_dir, run)
                    if not summary:
                        self._json({"error": "run 없음"}, 404)
                        return
                    self._json(summary)
                elif url.path == "/api/events":
                    q = parse_qs(url.query)
                    run = (q.get("run") or [""])[0]
                    offset = int((q.get("offset") or ["0"])[0])
                    if not _RUN_ID_RE.match(run):
                        self._json({"error": "잘못된 run id"}, 400)
                        return
                    path = find_run_path(out_dir, run)
                    if not path:
                        self._json({"error": "run 없음"}, 404)
                        return
                    self._json(read_new_events(path, offset))
                else:
                    self._json({"error": "not found"}, 404)
            except (ConnectionAbortedError, BrokenPipeError):
                pass   # 브라우저가 폴링을 끊은 것 — 정상
            except Exception as e:  # noqa: BLE001 — 서버는 죽지 않는다
                try:
                    self._json({"error": f"{type(e).__name__}: {e}"}, 500)
                except Exception:  # noqa: BLE001
                    pass

        def do_POST(self) -> None:   # noqa: N802
            url = urlparse(self.path)
            try:
                if url.path == "/api/sources/validate":
                    payload = self._body_json()
                    self._json(validate_source_payload(payload))
                elif url.path == "/api/docs-hub/validate":
                    payload = self._body_json()
                    self._json(validate_doc_target_payload(payload))
                elif url.path == "/api/sources":
                    payload = self._body_json()
                    validation = validate_source_payload(payload)
                    if not validation["ok"]:
                        self._json({"error": "필수값 누락", **validation}, 400)
                        return
                    source = store.upsert_source(payload, preserve_token=False)
                    self._json(enrich_sources([source], out_dir)[0], 201)
                elif url.path == "/api/docs-hub":
                    payload = self._body_json()
                    validation = validate_doc_target_payload(payload)
                    if not validation["ok"]:
                        self._json({"error": "필수값 누락", **validation}, 400)
                        return
                    target = store.upsert_doc_target(payload, preserve_token=False)
                    self._json(target, 201)
                elif url.path == "/api/docs-hub/submit-mr":
                    payload = self._body_json()
                    run = str(payload.get("run") or "")
                    target_id = str(payload.get("target") or "product-common")
                    if not _RUN_ID_RE.match(run):
                        self._json({"error": "잘못된 run id"}, 400)
                        return
                    plan = docs_hub_mr_plan(out_dir, store, run, target_id)
                    if not plan:
                        self._json({"error": "run 없음"}, 404)
                        return
                    if payload.get("dry_run", False):
                        self._json({"ok": True, "dry_run": True, "plan": plan})
                        return
                    if payload.get("confirm") != "product-common":
                        self._json({"error": "실제 MR 제출에는 confirm='product-common'이 필요합니다.", "plan": plan}, 400)
                        return
                    target = store.get_doc_target_private(target_id)
                    result = submit_gitlab_mr(plan, target=target or {}, out_dir=out_dir)
                    self._json({"ok": True, "plan": plan, "result": result}, 201)
                else:
                    self._json({"error": "not found"}, 404)
            except ValueError as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def do_PATCH(self) -> None:   # noqa: N802
            url = urlparse(self.path)
            try:
                m = re.match(r"^/api/sources/([A-Za-z0-9._-]+)$", url.path)
                if not m:
                    dm = re.match(r"^/api/docs-hub/([A-Za-z0-9._-]+)$", url.path)
                    if not dm:
                        self._json({"error": "not found"}, 404)
                        return
                    payload = self._body_json()
                    payload["id"] = dm.group(1)
                    validation = validate_doc_target_payload(payload)
                    if not validation["ok"]:
                        self._json({"error": "필수값 누락", **validation}, 400)
                        return
                    target = store.upsert_doc_target(payload, preserve_token=True)
                    self._json(target)
                    return
                payload = self._body_json()
                payload["id"] = m.group(1)
                validation = validate_source_payload(payload)
                if not validation["ok"]:
                    self._json({"error": "필수값 누락", **validation}, 400)
                    return
                source = store.upsert_source(payload, preserve_token=True)
                self._json(enrich_sources([source], out_dir)[0])
            except ValueError as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="wiki-pipeline 관측 대시보드")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--out", default=None, help="events JSONL 디렉터리 (기본: Settings.out_path)")
    args = parser.parse_args()

    if args.out:
        out_dir = Path(args.out).resolve()
    else:
        from ..common.config import load_settings
        settings = load_settings()
        out_dir = settings.out_path

    from ..common.config import load_settings
    settings = load_settings()
    store = ControlStore(default_db_path(out_dir))
    store.seed_from_settings(settings)

    server = ThreadingHTTPServer((args.host, args.port), make_handler(out_dir, store))
    print(f"관측 대시보드: http://{args.host}:{args.port}  (out={out_dir})")
    print("종료: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
