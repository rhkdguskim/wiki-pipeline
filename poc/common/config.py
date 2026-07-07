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

    # ── LLM (공급자 중립) ──
    llm_provider: str = "minimax"
    llm_base_url: str = "https://api.minimax.io/v1"
    llm_api_key: str = ""
    llm_model: str = "MiniMax-M3"
    llm_max_tokens: int = 8192
    llm_temperature: float = 0.2

    # ── 정적: 사내 GitLab ──
    gitlab_url: str = "http://wish.mirero.co.kr"
    gitlab_token: str = ""
    gitlab_token_header: str = "PRIVATE-TOKEN"
    gitlab_project_id: str = "947"
    static_from_sha: str = ""
    static_to_sha: str = ""
    static_themes: str = "intro,requirements,architecture-overview,component-diagram"

    # ── 매뉴얼: 원격제어 MCP ──
    mcp_endpoint_url: str = "http://110.110.10.70:9200/sse"
    mcp_transport: str = "sse"
    mcp_session_host: str = ""
    mcp_session_port: str = ""
    omniparser_url: str = ""

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
    def out_path(self) -> Path:
        p = (_POC_DIR / self.out_dir).resolve() if self.out_dir.startswith(".") else Path(self.out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


def load_settings() -> Settings:
    return Settings()
