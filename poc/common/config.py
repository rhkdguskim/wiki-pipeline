"""`.env` -> 타입있는 Settings 객체.

pydantic-settings로 자격증명·엔드포인트를 한 곳에서 로드한다. 자격증명은 코드에
하드코딩하지 않고 전부 여기(=`.env`)를 거친다 (위키 보안 제약).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from pydantic_settings import BaseSettings, SettingsConfigDict

# poc/ 디렉터리 기준으로 .env 를 찾는다 (실행 위치와 무관하게).
_POC_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _POC_DIR / ".env"


_SOURCE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _source_id(value: str) -> str:
    cleaned = _SOURCE_ID_RE.sub("-", value.strip()).strip("-").lower()
    return cleaned or "source"


@dataclass(frozen=True)
class SourceConfig:
    """문서화 대상 소스 저장소 1건.

    PoC는 GitLab 여러 개를 먼저 지원하고, kind 필드는 GitHub 커넥터를 붙일 자리다.
    """

    id: str
    kind: str
    url: str
    project_id: str
    token: str
    token_header: str = "PRIVATE-TOKEN"
    from_sha: str = ""
    to_sha: str = ""
    themes: str = ""
    label: str = ""

    @classmethod
    def from_dict(cls, raw: dict, *, fallback_themes: str) -> "SourceConfig":
        kind = str(raw.get("kind") or raw.get("scm") or "gitlab").lower()
        project_id = str(raw.get("project_id") or raw.get("project") or "").strip()
        label = str(raw.get("label") or raw.get("name") or project_id or kind).strip()
        sid = _source_id(str(raw.get("id") or label or project_id or kind))
        return cls(
            id=sid,
            kind=kind,
            url=str(raw.get("url") or raw.get("gitlab_url") or "").rstrip("/"),
            project_id=project_id,
            token=str(raw.get("token") or raw.get("gitlab_token") or ""),
            token_header=str(raw.get("token_header") or raw.get("gitlab_token_header") or "PRIVATE-TOKEN"),
            from_sha=str(raw.get("from_sha") or raw.get("static_from_sha") or ""),
            to_sha=str(raw.get("to_sha") or raw.get("static_to_sha") or ""),
            themes=str(raw.get("themes") or raw.get("static_themes") or fallback_themes),
            label=label,
        )


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
    scm_sources_json: str = ""
    source_id: str = ""
    source_label: str = ""
    source_kind: str = "gitlab"

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
    docshub_project_url: str = "http://wish.mirero.co.kr/mirero/project/pcc/product-common"
    docshub_project_path: str = "mirero/project/pcc/product-common"
    docshub_token: str = ""
    docshub_token_header: str = "PRIVATE-TOKEN"
    docshub_default_branch: str = "master"

    # ── 관측·출력 ──
    out_dir: str = "./out"
    log_level: str = "INFO"

    @property
    def theme_list(self) -> list[str]:
        return [t.strip() for t in self.static_themes.split(",") if t.strip()]

    @property
    def source_list(self) -> list[SourceConfig]:
        if self.scm_sources_json.strip():
            try:
                data = json.loads(self.scm_sources_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"SCM_SOURCES_JSON 파싱 실패: {e}") from e
            if not isinstance(data, list):
                raise ValueError("SCM_SOURCES_JSON 은 source 객체 배열이어야 합니다.")
            return [SourceConfig.from_dict(x, fallback_themes=self.static_themes)
                    for x in data if isinstance(x, dict)]
        if self.gitlab_url or self.gitlab_project_id or self.gitlab_token:
            return [SourceConfig(
                id=_source_id(self.source_id or self.gitlab_project_id or "gitlab"),
                kind="gitlab",
                url=self.gitlab_url,
                project_id=str(self.gitlab_project_id),
                token=self.gitlab_token,
                token_header=self.gitlab_token_header,
                from_sha=self.static_from_sha,
                to_sha=self.static_to_sha,
                themes=self.static_themes,
                label=self.source_label or f"GitLab {self.gitlab_project_id}",
            )]
        return []

    def get_source(self, source_id: str | None = None) -> SourceConfig | None:
        sources = self.source_list
        if not sources:
            return None
        if not source_id:
            return sources[0]
        wanted = _source_id(source_id)
        for source in sources:
            if source.id == wanted:
                return source
        known = ", ".join(s.id for s in sources)
        raise ValueError(f"알 수 없는 source '{source_id}'. 사용 가능: {known}")

    def for_source(self, source: SourceConfig, *, isolate_output: bool | None = None) -> "Settings":
        if source.kind != "gitlab":
            raise ValueError(f"아직 지원하지 않는 SCM kind: {source.kind}")
        multi = len(self.source_list) > 1
        scoped_out = self.out_dir
        if (isolate_output if isolate_output is not None else multi):
            base = self.out_path
            scoped_out = str(base / source.id)
        return self.model_copy(update={
            "gitlab_url": source.url,
            "gitlab_token": source.token,
            "gitlab_token_header": source.token_header,
            "gitlab_project_id": source.project_id,
            "static_from_sha": source.from_sha,
            "static_to_sha": source.to_sha,
            "static_themes": source.themes or self.static_themes,
            "source_id": source.id,
            "source_label": source.label or source.id,
            "source_kind": source.kind,
            "out_dir": scoped_out,
        })

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
