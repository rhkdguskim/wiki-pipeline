"""파이프라인 위치 상태 (last_processed_sha) — 일관성의 축.

위키 설계(decision-db-source-of-truth · concept-idempotent-sha)의 PoC 구현:
- "여기까지 문서화했다"는 포인터를 상태 파일에 기록한다.
- **성공 후에만 sha를 전진**시킨다 — 실패한 실행은 상태를 건드리지 않아 재실행이 안전(멱등).
- init 완료 -> last_processed_sha 기록 -> 이후 diff는 이 sha에서 HEAD까지 증분.
  (사용자 설계: init을 과거 시점으로 잡고 diff로 최신까지 올려 문서를 갱신하는 연계)

프로덕션에선 관리 서버 이력 DB가 SoT지만, PoC는 파일(out/_state.json)로 같은 계약을 구현한다.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

_STATE_FILE = "_state.json"


def _state_path(out_dir: Path) -> Path:
    return out_dir / _STATE_FILE


def load_state(out_dir: Path) -> dict | None:
    """상태 로드. 없거나 깨졌으면 None (= last_processed_sha null -> init 대상)."""
    p = _state_path(out_dir)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if data.get("last_processed_sha") else None


def save_state(
    out_dir: Path, *, project_id: str, last_processed_sha: str,
    ref: str, op: str, extra: dict | None = None,
) -> Path:
    """성공한 실행이 끝난 뒤에만 호출 — sha 포인터 전진."""
    p = _state_path(out_dir)
    prev = None
    if p.exists():
        try:
            prev = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = None
    data = {
        "project_id": str(project_id),
        "last_processed_sha": last_processed_sha,
        "ref": ref,
        "last_op": op,                       # "init" | "diff"
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "history": ((prev or {}).get("history") or [])[-9:] + [{
            "op": op, "sha": last_processed_sha,
            "at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }],
    }
    if extra:
        data.update(extra)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return p
