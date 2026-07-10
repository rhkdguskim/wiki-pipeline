"""시스템 설정 서비스 — DB 영구 저장 (ENT-F 후속 · LLM Settings).

.env 의존을 줄이고 대시보드에서 변경 가능하게 한다. 키는 "namespace.field"
형식 (예: "llm.provider", "llm.api_key"). 비밀 값도 v1 은 평문 저장.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SystemSetting
from ..timeutil import as_utc, isoformat_z

log = logging.getLogger("controlplane.settings")


class SettingsService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    # ── 단일 키 read/write ─────────────────────────────────

    def get(self, db: Session, key: str) -> Optional[str]:
        row = db.get(SystemSetting, key)
        return row.value if row else None

    def set(self, db: Session, key: str, value: str, *, actor: str = "") -> None:
        row = db.get(SystemSetting, key)
        if row is None:
            row = SystemSetting(key=key, value=value, updated_by=actor)
            db.add(row)
        else:
            row.value = value
            row.updated_by = actor
        db.flush()

    def delete(self, db: Session, key: str) -> bool:
        row = db.get(SystemSetting, key)
        if row is None:
            return False
        db.delete(row)
        db.flush()
        return True

    # ── LLM settings 전용 — DB 우선, .env 폴백 ──────────────

    _LLM_KEYS = [
        "llm.provider", "llm.base_url", "llm.api_key", "llm.model",
        "llm.max_tokens", "llm.temperature", "llm.timeout_sec",
        "llm.retry_attempts", "llm.max_concurrency",
    ]

    def _merge_llm(self, db: Session, env: dict[str, str]) -> tuple[dict[str, Any], str]:
        env_defaults = {
            "provider": env.get("LLM_PROVIDER", "openai-compatible"),
            "base_url": env.get("LLM_BASE_URL", ""),
            "api_key": env.get("LLM_API_KEY", ""),
            "model": env.get("LLM_MODEL", ""),
            "max_tokens": int(env.get("LLM_MAX_TOKENS", "65536")),
            "temperature": float(env.get("LLM_TEMPERATURE", "0.2")),
            "timeout_sec": float(env.get("LLM_TIMEOUT", "180")),
            "retry_attempts": int(env.get("LLM_RETRY_ATTEMPTS", "4")),
            # 공급자 동시 요청 한도(예: Z.AI=3). 0=무제한. 러너 concurrency 게이트가 강제.
            "max_concurrency": int(env.get("LLM_MAX_CONCURRENCY", "0")),
        }
        # DB 에 저장된 값으로 덮어쓰기 (있는 키만)
        db_values: dict[str, Any] = {}
        for db_key, env_key in [
            ("llm.provider", "provider"), ("llm.base_url", "base_url"),
            ("llm.api_key", "api_key"), ("llm.model", "model"),
        ]:
            v = self.get(db, db_key)
            if v is not None and v != "":
                db_values[env_key] = v
        # 숫자 필드는 int/float 변환 필요 — DB 에 문자열로 저장되므로.
        for db_key, env_key, caster in [
            ("llm.max_tokens", "max_tokens", int),
            ("llm.temperature", "temperature", float),
            ("llm.timeout_sec", "timeout_sec", float),
            ("llm.retry_attempts", "retry_attempts", int),
            ("llm.max_concurrency", "max_concurrency", int),
        ]:
            v = self.get(db, db_key)
            if v is not None and v != "":
                try:
                    db_values[env_key] = caster(v)
                except (TypeError, ValueError):
                    log.warning("invalid LLM setting in DB: %s=%r, env fallback", db_key, v)
        # 병합
        merged = dict(env_defaults)
        merged.update(db_values)
        # source 표시
        if not db_values:
            source = "env"
        elif set(db_values.keys()) == set(env_defaults.keys()):
            source = "db"
        else:
            source = "partial"
        return merged, source

    def get_llm_effective(self, db: Session, env: dict[str, str]) -> dict[str, Any]:
        """DB 값이 있으면 우선, 없으면 env 의 기본값.

        반환 키: provider, base_url, model, has_key, max_tokens,
                 temperature, timeout_sec, retry_attempts, source.
        `source` 는 "db" / "env" / "partial" — 어느 경로로 충족됐는지 운영 가시화.
        """
        merged, source = self._merge_llm(db, env)
        return {
            "provider": merged["provider"],
            "base_url": merged["base_url"],
            "model": merged["model"],
            "has_key": bool(merged["api_key"].strip()),
            "max_tokens": merged["max_tokens"],
            "temperature": merged["temperature"],
            "timeout_sec": merged["timeout_sec"],
            "retry_attempts": merged["retry_attempts"],
            "max_concurrency": merged["max_concurrency"],
            "source": source,
        }

    def get_llm_runtime_env(self, db: Session, env: dict[str, str]) -> dict[str, str]:
        """Data Plane runner env로 주입할 effective LLM 설정.

        API 응답과 달리 api_key 실제 값을 포함한다. 호출자는 이 dict를 로그나
        audit detail에 남기면 안 된다.
        """
        merged, _source = self._merge_llm(db, env)
        return {
            "LLM_PROVIDER": str(merged["provider"] or "openai-compatible"),
            "LLM_BASE_URL": str(merged["base_url"] or ""),
            "LLM_API_KEY": str(merged["api_key"] or ""),
            "LLM_MODEL": str(merged["model"] or ""),
            "LLM_MAX_TOKENS": str(int(merged["max_tokens"])),
            "LLM_TEMPERATURE": str(float(merged["temperature"])),
            "LLM_TIMEOUT": str(float(merged["timeout_sec"])),
            "LLM_RETRY_ATTEMPTS": str(int(merged["retry_attempts"])),
            "LLM_MAX_CONCURRENCY": str(int(merged["max_concurrency"])),
        }

    def set_llm(self, db: Session, payload: dict[str, Any], *, actor: str = "") -> dict[str, Any]:
        """UI 의 PATCH 페이로드로 LLM settings 저장. None / 빈 값은 env 폴백으로 복귀.

        반환: 갱신 후 effective settings (get_llm_effective 와 동일 형태).
        """
        # 빈 문자열이나 null 은 "삭제" 의미 — env 기본값으로 폴백.
        field_map = {
            "provider": "llm.provider",
            "base_url": "llm.base_url",
            "api_key": "llm.api_key",
            "model": "llm.model",
        }
        for env_key, db_key in field_map.items():
            if env_key in payload:
                v = payload[env_key]
                if v is None or v == "":
                    self.delete(db, db_key)
                else:
                    self.set(db, db_key, str(v), actor=actor)
        for env_key, db_key, caster in [
            ("max_tokens", "llm.max_tokens", int),
            ("temperature", "llm.temperature", float),
            ("timeout_sec", "llm.timeout_sec", float),
            ("retry_attempts", "llm.retry_attempts", int),
            ("max_concurrency", "llm.max_concurrency", int),
        ]:
            if env_key in payload:
                v = payload[env_key]
                if v is None or v == "":
                    self.delete(db, db_key)
                else:
                    # int/float 변환 에러를 잡아 명확한 400 사인.
                    # get_llm_effective와 동일한 에러 처리 규칙 적용.
                    try:
                        self.set(db, db_key, str(caster(v)), actor=actor)
                    except (TypeError, ValueError) as e:
                        raise ValueError(f"invalid {env_key}={v!r}: {e}") from e
        # 실제 환경변수로 env_dict를 빌드 — payload 기반이면 .env 폴백이 틀린다.
        # 사용자가 UI에서 max_tokens만 바꿔도 timeout 등은 .env 값이 그대로여야 함.
        import os
        env_dict = {
            "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "openai-compatible"),
            "LLM_BASE_URL": os.getenv("LLM_BASE_URL", ""),
            "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
            "LLM_MODEL": os.getenv("LLM_MODEL", ""),
            "LLM_MAX_TOKENS": os.getenv("LLM_MAX_TOKENS", "65536"),
            "LLM_TEMPERATURE": os.getenv("LLM_TEMPERATURE", "0.2"),
            "LLM_TIMEOUT": os.getenv("LLM_TIMEOUT", "180"),
            "LLM_RETRY_ATTEMPTS": os.getenv("LLM_RETRY_ATTEMPTS", "4"),
            "LLM_MAX_CONCURRENCY": os.getenv("LLM_MAX_CONCURRENCY", "0"),
        }
        return self.get_llm_effective(db, env_dict)

    def list_recent(self, db: Session, limit: int = 100) -> list[dict[str, Any]]:
        rows = db.scalars(
            select(SystemSetting).order_by(SystemSetting.updated_at.desc()).limit(limit)
        ).all()
        return [{
            "key": r.key,
            "value": r.value if r.key != "llm.api_key" else "(redacted)",
            "updated_at": isoformat_z(as_utc(r.updated_at)),
            "updated_by": r.updated_by,
        } for r in rows]
