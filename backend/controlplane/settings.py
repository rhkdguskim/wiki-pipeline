"""Control Plane 설정 — 공용 .env를 공유하되 서버 전용 키는 CONTROL_* 접두사."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class ControlPlaneSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore",
    )

    # ── 서버 ──
    control_host: str = "127.0.0.1"
    control_port: int = 8420

    # ── DB (decision-control-plane-postgresql) ──
    # 운영: postgresql+psycopg://user:pass@host:5432/wikipipeline
    # 개발 기본값: out/ 아래 SQLite (단일 프로세스 개발 편의)
    control_db_url: str = ""

    # ── 인증 (decision-server-vm-self-token) ──
    # "name:token,name2:token2" — 비우면 개발 모드(무인증, 기동 시 경고)
    control_api_tokens: str = ""
    # 러너 webhook 전용 토큰 (Data Plane -> Control Plane)
    control_runner_token: str = ""

    # ── 시크릿 at-rest 암호화 (Fernet key; 비우면 평문 저장 + 경고) ──
    control_secret_key: str = ""

    # ── 알림 (decision-email-alerting) ──
    notify_mode: str = "log"          # log | smtp
    admin_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "wiki-pipeline@localhost"
    smtp_starttls: bool = True

    # ── 스케줄 기본값 (decision-nightly-batch: 평일 20:00) ──
    default_schedule_cron: str = "0 20 * * 1-5"
    scheduler_enabled: bool = True

    # ── 산출물 루트 (레거시 JSONL run 조회용 — common.Settings.out_dir과 동일 규칙) ──
    out_dir: str = "./out"

    @property
    def out_path(self) -> Path:
        p = (_BACKEND_DIR / self.out_dir).resolve() if self.out_dir.startswith(".") else Path(self.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        if self.control_db_url.strip():
            return self.control_db_url.strip()
        return f"sqlite:///{self.out_path / 'control-plane.sqlite'}"

    @property
    def api_token_map(self) -> dict[str, str]:
        """{token: name} — 조회는 토큰 기준."""
        out: dict[str, str] = {}
        for pair in self.control_api_tokens.split(","):
            pair = pair.strip()
            if not pair:
                continue
            name, _, token = pair.partition(":")
            if token:
                out[token.strip()] = name.strip()
        return out


def load_cp_settings() -> ControlPlaneSettings:
    return ControlPlaneSettings()
