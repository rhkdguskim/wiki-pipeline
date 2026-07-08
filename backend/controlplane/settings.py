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
    default_schedule_cron: str = "0 20 * * mon-fri"
    scheduler_enabled: bool = True

    # ── 매뉴얼 파이프라인 태그 폴링 (decision-release-tag-trigger) ──
    # 비우면 폴링 안 함. 기본값: 30분마다. prod 부하가 크면 늘릴 것.
    manual_tag_poll_cron: str = ""
    manual_tag_poll_enabled: bool = False

    # ── CORS 허용 origin (decision-server-vm-self-token · 프런트 대시보드) ──
    # 쉼표 구분. 비워도(*로 기본 동작) 개발은 가능하나 prod 에서는 명시 권장.
    control_cors_origins: str = ""

    # ── WS 이벤트 필터 (Track E) ──
    # true: WS 기본이 모든 이벤트 수신(thinking 포함, 과거 동작).
    # false(권장): WS 기본이 agent_step.thinking 드랍 — 모니터링 노이즈 감소.
    # 클라이언트가 ?verbose=1|0 으로 명시하면 설정보다 우선.
    control_ws_default_verbose: bool = False

    # ── 토큰 순환 경고 (question-cloud-scm-token-policy) ──
    # scm_instances.token_rotated_at 기준 N일 임박 시 admin 이메일. 0=비활성.
    token_rotation_warn_days: int = 0

    # ── daily digest (question-batch-observability 잔량) ──
    # 비우면 발송 안 함. 매일 08:00에 전일 run 요약을 admin·owner 에게 발송.
    daily_digest_cron: str = ""
    daily_digest_enabled: bool = False

    # ── 이벤트 보존 정책 — 완료 run의 상세 이벤트를 N일 후 정리 (0=무제한) ──
    event_retention_days: int = 30

    # ── 산출물 루트 (레거시 JSONL run 조회용 — common.Settings.out_dir과 동일 규칙) ──
    out_dir: str = "./out"

    # ── 운영 ──
    # LOG_LEVEL — uvicorn.access / uvicorn.error / app 로거 공통 레벨.
    # common.config.Settings.log_level 와 의미가 같지만 ControlPlane 에서도
    # 직접 읽기 때문에 중복 정의.
    log_level: str = "INFO"
    # LOG_FORMAT=json|text — 운영에선 json 으로 (수집 친화). 개발은 text.
    log_format: str = "text"
    # GRACEFUL_SHUTDOWN_TIMEOUT_SEC — uvicorn 종료 시 inflight 요청·runner 종료 대기
    graceful_shutdown_timeout_sec: float = 30.0
    # RATE_LIMIT_PER_MIN — API 토큰 분당 요청 한도 (0=비활성).
    rate_limit_per_min: int = 600
    # AUDIT_LOG_RETENTION_DAYS — audit_logs 테이블 보존 (0=영구)
    audit_log_retention_days: int = 365
    # DEEP_HEALTHCHECK_TIMEOUT_SEC — /health/ready 의 서브 체크 타임아웃
    deep_healthcheck_timeout_sec: float = 3.0

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
