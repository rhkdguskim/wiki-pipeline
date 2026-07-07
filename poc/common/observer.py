"""custom 스트림 수신 -> 콘솔(계층 들여쓰기) + JSONL 싱크.

emit()이 방출한 ProgressEvent를 사람이 읽는 콘솔과 감사용 JSONL 두 곳으로 흘린다.
JSONL은 out/events-{run_id}.jsonl. 대시보드는 나중에 이 JSONL/webhook을 소비.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Any

# Windows 콘솔(cp949)에서도 UTF-8 출력. 재구성 실패해도 무해.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_LAYER_INDENT = {"run": 0, "stage": 1, "engine_call": 2, "agent_step": 3}
_STATUS_MARK = {"running": ".", "done": "OK", "failed": "XX"}
_KIND_MARK = {"thinking": "[think]", "tool_use": "[tool]", "tool_result": "[<-]",
              "usage": "[usage]", "llm_retry": "[retry]"}


class Observer:
    def __init__(self, run_id: str, out_dir: Path):
        self.run_id = run_id
        self.jsonl_path = out_dir / f"events-{run_id}.jsonl"
        self._fh = self.jsonl_path.open("a", encoding="utf-8")
        # map/reduce가 병렬 스레드에서 sink()를 부르므로 라인 단위 원자성을 Lock으로 보장.
        self._lock = threading.Lock()

    def sink(self, event: dict[str, Any]) -> None:
        """이벤트 1건을 콘솔+JSONL로. 러너·노드·병렬 워커 어디서든 호출 가능 (스레드 안전)."""
        line = self._format(event)
        payload = json.dumps(event, ensure_ascii=False) + "\n"
        with self._lock:
            # JSONL (감사 추적) — Lock 안에서 write+flush 해 라인 인터리브 방지.
            self._fh.write(payload)
            self._fh.flush()
            # 콘솔 (계층 들여쓰기) — 인코딩 실패해도 죽지 않게 방어.
            try:
                print(line)
            except UnicodeEncodeError:
                print(line.encode("ascii", "replace").decode("ascii"))

    def _format(self, e: dict[str, Any]) -> str:
        indent = "  " * _LAYER_INDENT.get(e.get("layer", "run"), 0)
        mark = _STATUS_MARK.get(e.get("status", "running"), "·")
        stage = e.get("stage", "")
        prog = e.get("progress") or {}
        prog_s = f" [{prog['n']}/{prog['m']} {prog.get('unit','')}]" if prog.get("m") else ""
        detail = e.get("detail") or {}
        detail_s = self._format_detail(detail)
        return f"{indent}{mark} {stage}{prog_s}{detail_s}"

    @staticmethod
    def _format_detail(d: dict[str, Any]) -> str:
        kind = d.get("kind")
        mark = _KIND_MARK.get(kind, "")
        if kind == "thinking":
            return f"  {mark} {d.get('summary', '')[:120]}"
        if kind == "tool_use":
            return f"  {mark} {d.get('tool')}({_short(d.get('input'))})"
        if kind == "tool_result":
            ok = "ok" if d.get("ok") else "ERR"
            return f"  {mark} {ok} {d.get('preview', '')[:80]}"
        if kind == "usage":
            return f"  {mark} in={d.get('input_tokens')} out={d.get('output_tokens')}"
        if kind == "llm_retry":
            return f"  {mark} attempt={d.get('attempt')} ({d.get('error')})"
        return ""

    def emitter(self, pipeline_id: str, run_id: str):
        """러너(노드 밖)용 방출 클로저 — make_event + sink 표준 경로.

        노드 안은 events.emit()(custom 스트림), 노드 밖 결정적 러너는 이 클로저를 쓴다.
        두 파이프라인 러너가 같은 모양의 rev()를 각자 만들던 것을 공용화.
        """
        from . import events as ev

        def rev(layer, stage, status="running", progress=None, detail=None):
            self.sink(ev.make_event(
                pipeline_id=pipeline_id, run_id=run_id, layer=layer,
                stage=stage, status=status, progress=progress, detail=detail,
            ))

        return rev

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


def _short(v: Any, n: int = 60) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n] + "…"
