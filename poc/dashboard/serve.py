"""관측 대시보드 서버 — 표준 라이브러리만으로 events JSONL을 증분 서빙.

    python -m poc.dashboard.serve            # http://127.0.0.1:8420
    python -m poc.dashboard.serve --port 9000 --out D:/path/to/out

API (모두 GET, JSON):
- /            : 대시보드 페이지 (index.html)
- /api/runs    : out/events-*.jsonl 목록 [{run_id, size, age_sec}] (최신순)
- /api/events?run=<id>&offset=<bytes>
               : offset 이후의 완결 라인만 파싱해 반환 {events, offset, size, age_sec}
                 offset 프로토콜이라 파일이 커져도 폴링 비용은 증분뿐이다.

파이프라인 프로세스와 완전 분리 — observer가 flush하는 파일을 읽기만 하므로
실행 중인 run이든 끝난 run이든 같은 경로로 본다. 쓰기 API는 없다.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MAX_CHUNK = 4 * 1024 * 1024   # 폴링 1회 최대 읽기 (초기 따라잡기는 클라이언트가 반복 호출)
_HTML_PATH = Path(__file__).resolve().parent / "index.html"


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


def list_runs(out_dir: Path) -> list[dict]:
    runs = []
    for p in out_dir.glob("events-*.jsonl"):
        run_id = p.name[len("events-"):-len(".jsonl")]
        st = p.stat()
        runs.append({
            "run_id": run_id,
            "size": st.st_size,
            "age_sec": round(time.time() - st.st_mtime, 1),
        })
    runs.sort(key=lambda r: r["age_sec"])
    return runs


def make_handler(out_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):   # noqa: N802 — 폴링 로그로 콘솔이 잠기는 것 방지
            pass

        def _json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:   # noqa: N802 — http.server 계약
            url = urlparse(self.path)
            try:
                if url.path in ("/", "/index.html"):
                    body = _HTML_PATH.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif url.path == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                elif url.path == "/api/runs":
                    self._json(list_runs(out_dir))
                elif url.path == "/api/events":
                    q = parse_qs(url.query)
                    run = (q.get("run") or [""])[0]
                    offset = int((q.get("offset") or ["0"])[0])
                    if not _RUN_ID_RE.match(run):
                        self._json({"error": "잘못된 run id"}, 400)
                        return
                    path = out_dir / f"events-{run}.jsonl"
                    if not path.is_file():
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
        out_dir = load_settings().out_path

    server = ThreadingHTTPServer((args.host, args.port), make_handler(out_dir))
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
