"""MCP 브리지 — SSE 연결 + 도구 로드 + 동기 래핑 (공용 런타임).

entity-remote-control-mcp 실측: MiVncManagerMcpServer(SSE :9200) / MiVncMcpServer(:9100)가
vnc-mcp-lib 도구(스크린샷·클릭·UIA 트리·터미널·파일전송 등 60여 개)를 SSE/stdio로 노출한다.

langchain-mcp-adapters가 만드는 도구는 async 전용(coroutine만 바인딩)이라, common/graph.py의
동기 tool-use 루프에 물리기 위해 배경 스레드에 이벤트 루프를 상주시켜 브리지한다.

이 모듈은 파이프라인을 모른다 — 접속 파라미터는 생성자 인자로, 호출 기록은 on_record
콜백으로 주입받는다. 매뉴얼 파이프라인은 모든 도구 호출(에이전트 자율 탐색·시나리오
결정 실행 불문)을 이 콜백으로 ObservationLog에 모은다 (concept-observation-grounding).
스크린샷 등 대형 base64 결과는 shots_dir에 파일로 빼고 마커 텍스트로 대체한다
(텍스트 LLM 컨텍스트 보호 + "캡처" 관측 보존).
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import concurrent.futures as cf
import json
import threading
from pathlib import Path
from typing import Callable

from langchain_core.tools import BaseTool, StructuredTool

def _max_tool_chars() -> int:
    from .config import cached_settings
    return cached_settings().mcp_max_tool_chars
def _b64_min() -> int:
    from .config import cached_settings
    return cached_settings().mcp_b64_min
_B64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\r\n")

_DESTRUCTIVE_TOOL_KEYWORDS = (
    "delete", "save", "terminal", "file_write", "close_app", "install",
    "remove", "rm", "drop", "reset", "shutdown", "kill", "force",
)

# 도구 호출 1건의 기록 콜백: (tool, args, ok, preview) -> None
RecordFn = Callable[[str, dict, bool, str], None]


class McpBridge:
    """MCP 세션 1개를 배경 이벤트 루프에 상주시키고 동기 인터페이스로 노출한다.

    create_session 컨텍스트는 anyio 태스크 스코프 제약(진입·이탈이 같은 태스크) 때문에
    단일 코루틴(_run_session) 안에서 열고 닫는다. 도구 호출은 그 루프에
    run_coroutine_threadsafe로 던져 동기 결과를 받는다.
    """

    def __init__(self, *, endpoint_url: str, transport: str, shots_dir: Path,
                 run_id: str, tool_timeout: float = 90.0,
                 on_record: RecordFn | None = None):
        self._endpoint_url = endpoint_url
        self._transport = transport
        self._tool_timeout = tool_timeout
        self._on_record = on_record
        self._shots_dir = shots_dir
        self._run_id = run_id
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="mcp-bridge", daemon=True)
        self._session_fut: cf.Future | None = None
        self._stop: asyncio.Event | None = None
        self._raw_tools: dict[str, BaseTool] = {}
        self._shot_seq = 0

    # ── 연결 수명 ──

    def connect(self, timeout: float = 60.0) -> list[str]:
        """SSE 연결 + initialize + 도구 로드. 도구 이름 목록 반환 (L1 검증 지점)."""
        self._thread.start()
        ready: cf.Future = cf.Future()
        self._session_fut = asyncio.run_coroutine_threadsafe(
            self._run_session(ready), self._loop)
        return ready.result(timeout=timeout)

    async def _run_session(self, ready: cf.Future) -> None:
        from langchain_mcp_adapters.sessions import create_session
        from langchain_mcp_adapters.tools import load_mcp_tools

        conn = {"transport": self._transport, "url": self._endpoint_url}
        self._stop = asyncio.Event()
        try:
            async with create_session(conn) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                self._raw_tools = {t.name: t for t in tools}
                ready.set_result(sorted(self._raw_tools))
                await self._stop.wait()
        except BaseException as e:  # noqa: BLE001 — 연결 실패를 connect() 호출부로 전달
            if not ready.done():
                ready.set_exception(e)
            else:
                raise

    def close(self) -> None:
        try:
            if self._stop is not None:
                self._loop.call_soon_threadsafe(self._stop.set)
            if self._session_fut is not None:
                self._session_fut.result(timeout=10)
        except Exception:
            pass
        finally:
            if self._thread.is_alive():
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=5)

    # ── 도구 호출 (동기) ──

    def tool_names(self) -> list[str]:
        return sorted(self._raw_tools)

    def _record(self, tool: str, args: dict, ok: bool, preview: str) -> None:
        if self._on_record is not None:
            self._on_record(tool, args, ok, preview)

    def call(self, name: str, args: dict) -> tuple[bool, str]:
        """도구 1회 호출 — 결과를 텍스트로 강제하고 on_record 콜백에 기록.

        실패도 예외 대신 오류 텍스트로 반환한다(정적 read_file과 같은 계약) —
        에이전트가 스스로 정정할 수 있고, 시나리오 러너는 다음 스텝으로 진행한다.
        """
        tool = self._raw_tools.get(name)
        if tool is None:
            text = f"[도구 없음] {name} — 연결된 MCP 서버 도구 목록에 없다"
            self._record(name, args, False, text)
            return False, text
        try:
            fut = asyncio.run_coroutine_threadsafe(tool.ainvoke(args), self._loop)
            raw = fut.result(timeout=self._tool_timeout)
            ok, text = True, self._coerce(raw)
        except Exception as e:  # noqa: BLE001
            ok, text = False, f"[{name} 실패] {type(e).__name__}: {e}"
        if len(text) > _max_tool_chars():
            text = text[:_max_tool_chars()] + f"\n[...{len(text) - _max_tool_chars()}자 생략...]"
        self._record(name, args, ok, text)
        return ok, text

    def sync_tools(self, allowlist: list[str] | None = None, *,
                   strict: bool = False) -> list[BaseTool]:
        """에이전트 바인딩용 — async MCP 도구를 동기 StructuredTool로 랩핑.

        allowlist는 정확한 도구 이름으로만 매칭한다. 부분 문자열 매칭은 넓은
        토큰(예: file)이 파괴적 도구(file_delete)를 우연히 허용할 수 있어 금지한다.

        strict=True 면 allowlist 가 비어 있을 때 ValueError 를 발생시킨다
        (production manual run 은 allowlist 필수 — preflight 실패).

        파괴적 도구(delete, save, terminal, file_write, close_app, install 등)는
        allowlist 에 명시적으로 포함되지 않는 한 항상 차단한다.
        """
        names = self.tool_names()
        if allowlist:
            allow_lower = {a.lower() for a in allowlist}
            names = [n for n in names if n.lower() in allow_lower]
        elif strict:
            raise ValueError(
                "tool_allowlist 가 비어 있습니다 — production manual run 은 "
                "allowlist 가 필수입니다. 소스의 manual profile 을 확인하세요."
            )
        names = [n for n in names if not self._is_destructive(n, allowlist)]
        if strict and not names:
            raise ValueError(
                "tool_allowlist 에 현재 MCP 서버가 제공하는 안전한 도구가 없습니다"
            )
        return [self._wrap(self._raw_tools[n]) for n in names]

    @staticmethod
    def _is_destructive(name: str, allowlist: list[str] | None) -> bool:
        """파괴적 도구를 판별 — allowlist 에 명시적 포함 시 허용."""
        if allowlist:
            name_lower = name.lower()
            if name_lower in {a.lower() for a in allowlist}:
                return False
        name_lower = name.lower()
        return any(kw in name_lower for kw in _DESTRUCTIVE_TOOL_KEYWORDS)

    def _wrap(self, tool: BaseTool) -> StructuredTool:
        def _call(**kwargs) -> str:
            _ok, text = self.call(tool.name, kwargs)
            return text

        return StructuredTool(
            name=tool.name,
            description=tool.description or tool.name,
            args_schema=tool.args_schema,   # MCP inputSchema(dict JSON Schema) 그대로
            func=_call,
        )

    # ── 결과 텍스트 강제 (스크린샷 등 바이너리 방어) ──

    def _coerce(self, raw) -> str:
        if isinstance(raw, tuple):   # (content, artifact) 형식 방어
            raw = raw[0]
        if isinstance(raw, str):
            return self._extract_blob(raw)
        if isinstance(raw, list):
            parts = []
            for item in raw:
                if isinstance(item, str):
                    parts.append(self._extract_blob(item))
                elif isinstance(item, dict):
                    parts.append(self._image_or_json(item))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        if isinstance(raw, dict):
            return self._image_or_json(raw)
        return str(raw)

    def _image_or_json(self, item: dict) -> str:
        """콘텐츠 블록 dict 처리 — text 블록은 본문만, image 블록은 파일로."""
        kind = str(item.get("type", ""))
        if kind == "text" and isinstance(item.get("text"), str):
            return self._extract_blob(item["text"])
        mime = str(item.get("mimeType") or item.get("mime_type") or "")
        data = item.get("data") or item.get("base64")
        if isinstance(data, str) and len(data) > 1000 and ("image" in mime or kind == "image"):
            return self._save_shot(data, mime)
        return json.dumps(item, ensure_ascii=False)[:2000]

    def _extract_blob(self, text: str) -> str:
        """본문 전체가 거대 base64(이미지 원문 반환형 서버)면 파일로 빼고 마커로."""
        if len(text) >= _b64_min():
            head = text[:120].strip()
            if head and all(c in _B64_CHARS for c in head):
                return self._save_shot(text.strip())
        return text

    def _save_shot(self, b64: str, mime: str = "image/png") -> str:
        self._shot_seq += 1
        ext = "png" if "png" in mime else ("jpg" if "jp" in mime else "bin")
        path = self._shots_dir / f"shot-{self._run_id}-{self._shot_seq:03d}.{ext}"
        try:
            self._shots_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(b64))
            return f"[스크린샷 저장: shots/{path.name}]"
        except (binascii.Error, ValueError, OSError) as e:
            return f"[스크린샷 저장 실패: {type(e).__name__}] (base64 {len(b64)}자)"
