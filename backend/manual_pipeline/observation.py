"""관측 로그 — 순회가 수집하는 화면·컨트롤·전이·캡처의 감사 추적.

concept-observation-grounding: 매뉴얼의 주장은 코드 추론이 아니라 이 로그에 기록된
관측 사실에만 매단다. 모든 MCP 도구 호출(시나리오·자율 탐색 불문)이 mcp_client 브리지를
거치며 여기 기록되고, JSONL(out/manual/observations-{run_id}.jsonl)로 저장돼
중단 재개(resume) 시 그대로 복원된다.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_PREVIEW_CHARS = 1500   # 관측 1건당 결과 미리보기 상한 (근거 블록용)

_SECRET_VALUE_RE = re.compile(
    r"((?:password|passwd|pwd|token|access_token|refresh_token|"
    r"api[_-]?key|apikey|secret|authorization)\s*[=:]\s*)"
    r"(?:bearer\s+)?(\S+)",
    re.IGNORECASE,
)

_CREDENTIAL_KEYS = frozenset({
    "password", "passwd", "pwd", "token", "access_token",
    "refresh_token", "api_key", "apikey", "secret", "authorization",
})


def _redact(value: str) -> str:
    """credential-like 패턴을 마스킹한다. 비밀번호·토큰·API 키 등."""
    if not value or not isinstance(value, str):
        return value
    return _SECRET_VALUE_RE.sub(lambda m: m.group(1) + "***REDACTED***", value)


def _redact_args(args: dict) -> dict:
    """args dict 의 값 중 credential-like 문자열을 마스킹한다.

    키가 credential 이름(password, token 등)이면 값을 직접 마스킹한다.
    값이 문자열이면 내부의 credential 패턴도 마스킹한다.
    """
    redacted: dict = {}
    for k, v in args.items():
        if isinstance(k, str) and k.lower() in _CREDENTIAL_KEYS:
            redacted[k] = "***REDACTED***"
        elif isinstance(v, str):
            redacted[k] = _redact(v)
        elif isinstance(v, dict):
            redacted[k] = _redact_args(v)
        else:
            redacted[k] = v
    return redacted


@dataclass
class Observation:
    seq: int          # o1, o2, ... 근거 인용 태그
    phase: str        # "scenario:<id>" | "explore" | "smoke" | "setup"
    tool: str
    args: dict
    ok: bool
    preview: str      # 도구 결과 앞부분 (스크린샷은 저장 경로 마커로 대체됨)
    ts: str


class ObservationLog:
    def __init__(self, path: Path, items: list[Observation] | None = None):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.items: list[Observation] = items or []
        self.phase = "setup"
        self._fh = path.open("a", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ObservationLog":
        """기존 JSONL을 복원해 이어서 기록 (resume 경로). 파일 없으면 새로 시작."""
        items: list[Observation] = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    items.append(Observation(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return cls(path, items)

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def record(self, *, tool: str, args: dict, ok: bool, preview: str) -> Observation:
        safe_args = _redact_args(args)
        safe_preview = _redact(preview[:_PREVIEW_CHARS])
        obs = Observation(
            seq=len(self.items) + 1, phase=self.phase, tool=tool, args=safe_args,
            ok=ok, preview=safe_preview,
            ts=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        )
        self.items.append(obs)
        self._fh.write(json.dumps(asdict(obs), ensure_ascii=False) + "\n")
        self._fh.flush()
        return obs

    def scenario_ran(self, scenario_id: str) -> bool:
        """이 시나리오의 관측 기록이 이미 있는가 (resume 시 결정적 재실행 회피)."""
        tag = f"scenario:{scenario_id}"
        return any(o.phase == tag for o in self.items)

    def evidence_block(self, max_chars: int = 80000) -> str:
        """writer/critic 프롬프트에 넣을 근거 블록. [oN|phase] tool(args) -> OK/ERR + 결과."""

        def build(cut: int | None) -> str:
            lines = []
            for o in self.items:
                a = json.dumps(_redact_args(o.args), ensure_ascii=False)
                if len(a) > 160:
                    a = a[:160] + "…"
                p = _redact(o.preview if cut is None else o.preview[:cut])
                lines.append(f"[o{o.seq}|{o.phase}] {o.tool}({a}) -> "
                             f"{'OK' if o.ok else 'ERR'}\n{p}")
            return "\n\n".join(lines)

        block = build(None)
        if len(block) > max_chars:
            block = build(400)
        if len(block) > max_chars:
            head = block[: int(max_chars * 0.6)]
            tail = block[-int(max_chars * 0.35):]
            block = head + "\n\n[...중략: 관측 로그가 길어 일부 생략...]\n\n" + tail
        return block or "(관측 없음)"

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass
