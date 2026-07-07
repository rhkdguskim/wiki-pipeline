"""`.env` -> 타입있는 Settings 객체.

pydantic-settings로 자격증명·엔드포인트를 한 곳에서 로드한다. 자격증명은 코드에
하드코딩하지 않고 전부 여기(=`.env`)를 거친다 (위키 보안 제약).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# poc/ 디렉터리 기준으로 .env 를 찾는다 (실행 위치와 무관하게).
_POC_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _POC_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM (공급자 중립 — 공급자·엔드포인트·모델은 전부 .env로) ──
    llm_provider: str = "openai-compatible"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_max_tokens: int = 65536
    llm_temperature: float = 0.2
    llm_timeout: float = 180.0

    # ── 정적: GitLab (대상 인스턴스·프로젝트는 전부 .env로 — 코드에 특정 레포 가정 없음) ──
    gitlab_url: str = ""
    gitlab_token: str = ""
    gitlab_token_header: str = "PRIVATE-TOKEN"
    gitlab_project_id: str = ""
    static_from_sha: str = ""
    static_to_sha: str = ""
    static_themes: str = "intro,requirements,architecture-overview,component-diagram"

    # ── 매뉴얼: 원격제어 MCP (endpoint는 .env로) ──
    mcp_endpoint_url: str = ""
    mcp_transport: str = "sse"
    mcp_session_host: str = ""
    mcp_session_port: str = ""
    omniparser_url: str = ""

    # ── 매뉴얼: 순회·생성 ──
    manual_scenario_file: str = "./manual_pipeline/scenarios/sample.json"
    manual_themes: str = "user-manual,operator-manual"
    manual_explore_steps: int = 12       # 자율 탐색 도구 호출 예산
    manual_tool_allowlist: str = ""      # 비우면 MCP 도구 전체 노출 (토큰 매칭, 쉼표구분)
    manual_tool_timeout: float = 90.0    # 도구 1회 호출 타임아웃(초)

    # ── docs-hub (PoC=스텁) ──
    docshub_mr_enabled: bool = False
    docshub_project_id: str = ""

    # ── 관측·출력 ──
    out_dir: str = "./out"
    log_level: str = "INFO"

    @property
    def theme_list(self) -> list[str]:
        return [t.strip() for t in self.static_themes.split(",") if t.strip()]

    @property
    def manual_theme_list(self) -> list[str]:
        return [t.strip() for t in self.manual_themes.split(",") if t.strip()]

    @property
    def manual_scenario_path(self) -> Path:
        p = Path(self.manual_scenario_file)
        return p if p.is_absolute() else (_POC_DIR / p).resolve()

    @property
    def manual_allowlist(self) -> list[str]:
        return [t.strip().lower() for t in self.manual_tool_allowlist.split(",") if t.strip()]

    @property
    def out_path(self) -> Path:
        p = (_POC_DIR / self.out_dir).resolve() if self.out_dir.startswith(".") else Path(self.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


def load_settings() -> Settings:
    return Settings()
