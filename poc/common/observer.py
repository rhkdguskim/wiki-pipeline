"""custom 스트림 수신 -> 콘솔(계층 들여쓰기) + JSONL 싱크.

emit()이 방출한 ProgressEvent를 사람이 읽는 콘솔과 감사용 JSONL 두 곳으로 흘린다.
JSONL은 out/events-{run_id}.jsonl. 대시보드는 나중에 이 JSONL/webhook을 소비.
"""
from __future__ import annotations

import json
import sys
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

    def sink(self, event: dict[str, Any]) -> None:
        """이벤트 1건을 콘솔+JSONL로. 러너·노드 양쪽에서 호출 가능."""
        # JSONL (감사 추적)
        self._fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._fh.flush()
        # 콘솔 (계층 들여쓰기) — 인코딩 실패해도 죽지 않게 방어.
        line = self._format(event)
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

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass


def _short(v: Any, n: int = 60) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n] + "…"
