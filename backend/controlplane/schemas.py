"""OpenAPI 응답 스키마 (ENT-J) — 주요 엔드포인트의 Pydantic 모델.

FastAPI 가 이 모델을 response_model 로 받으면 자동 검증 + OpenAPI 스키마에
스키마 정의가 포함된다. 기존 dict 반환 엔드포인트는 그대로 두되, 계약이 안정된
핵심 엔드포인트만 명시적 스키마를 갖도록 한다.

확장 시점: 프런트가 새 필드를 요구하거나 외부 사용자가 생기면 그 엔드포인트에
response_model 을 추가한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    # response_model 검증 — 알 수 없는 필드는 무시(스키마 진화 시 호환).
    # summarize_events 는 kpi·stages·timeline 외에 tools·usage_by_model·errors·
    # warnings·generated·artifacts 도 돌려주는데, 그 전부를 매번 스키마에 적는 건
    # brittle. extra="ignore" 로 두고 핵심 필드만 validation 대상으로 둔다.
    model_config = ConfigDict(extra="ignore", from_attributes=True)


# ── runs ───────────────────────────────────────────────────────

class RunView(_Base):
    run_id: str
    source_id: str
    pipeline_id: str
    mode: str
    branch_role: str
    trigger: str
    status: str
    from_sha: str = ""
    to_sha: str = ""
    doc_count: int = 0
    mr_url: str = ""
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: str
    updated_at: str
    attempt: int = 1
    publishable: bool = False
    publish_state: str = "unknown"
    quality_status: str = "not_evaluated"
    quality_score: Optional[int] = None
    blocked_reason: str = ""
    release_tag: str = ""
    artifact_version: str = ""
    snapshot_version: int = 0
    stale_complete: bool = False
    heartbeat_at: str = ""
    started_at: str = ""
    terminal_at: str = ""


class RunSummary(_Base):
    run_id: str
    source_id: str
    pipeline_id: str
    branch_role: str = ""
    status: str
    current_stage: str = ""
    started_at: str = ""
    last_event_at: str = ""
    duration_sec: Optional[float] = None
    event_count: int = 0
    from_sha: str = ""
    to_sha: str = ""
    mr_url: str = ""
    doc_count: int = 0
    error: str = ""
    kpi: dict[str, Any] = Field(default_factory=dict)
    stages: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    publishable: bool = False
    publish_state: str = "unknown"
    blocked_reason: str = ""
    quality_status: str = "not_evaluated"
    quality_score: Optional[int] = None
    warning_publish_policy: str = "review_required"
    release_tag: str = ""
    artifact_version: str = ""
    snapshot_version: int = 0
    stale_complete: bool = False
    heartbeat_at: str = ""
    terminal_at: str = ""
    attempt: int = 1
    quality: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    artifact: dict[str, Any] = Field(default_factory=dict)
    vnc: dict[str, Any] = Field(default_factory=dict)
    mr: dict[str, Any] = Field(default_factory=dict)


# ── pipelines (Track F) ──────────────────────────────────────

class PipelineStatusEntry(_Base):
    source_id: str
    pipeline_id: str
    last_run_id: str = ""
    last_status: str = ""
    last_run_at: str = ""
    last_error: str = ""
    last_mr_url: str = ""
    last_doc_count: int = 0
    success_window: int = 0
    failed_window: int = 0
    running: int = 0
    total_tokens_window: int = 0
    mean_duration_sec: Optional[float] = None
    enabled_schedule: bool = False


class PipelineStatusResponse(_Base):
    window_hours: int
    pipelines: list[PipelineStatusEntry]
    generated_at: str


# ── sources / instances / docs-hub ────────────────────────────

class SourceView(_Base):
    id: str
    label: str
    kind: str
    instance_id: str = ""
    repo: str
    doc_dir: str = ""
    themes: str = ""
    owner_email: str = ""
    schedule_cron: str = ""
    enabled: bool = True
    disabled_reason: str = ""
    dev_branch: str = ""
    release_branch: str = ""
    last_processed_sha: str = ""
    has_token: bool = False


class InstanceView(_Base):
    id: str
    kind: str
    label: str
    base_url: str
    token_header: str = "PRIVATE-TOKEN"
    has_token: bool = False
    enabled: bool = True
    updated_at: str = ""


class DocTargetView(_Base):
    id: str
    label: str
    kind: str
    url: str
    project_id: str = ""
    project_path: str = ""
    default_branch: str = "master"
    enabled: bool = False
    has_token: bool = False
    updated_at: str = ""


# ── audit (ENT-F) ────────────────────────────────────────────

class AuditEntry(_Base):
    id: int
    ts: str
    actor: str
    action: str
    target_kind: str = ""
    target_id: str = ""
    request_id: str = ""
    detail: str = ""
    remote_addr: str = ""


class AuditRecentResponse(_Base):
    entries: list[AuditEntry]
    limit: int


# ── health ────────────────────────────────────────────────────

class HealthCheckResult(_Base):
    ok: bool
    detail: str = ""


class HealthResponse(_Base):
    status: str
    checks: dict[str, HealthCheckResult] = Field(default_factory=dict)
    ts: str = ""


# ── MR plan ──────────────────────────────────────────────────

class MRFileChange(_Base):
    local_path: str
    target_path: str
    size: int = 0
    action: str = "upsert"


class MRPlanView(_Base):
    run_id: str
    source_id: str
    source_label: str
    target: dict[str, Any]
    base_branch: str
    branch_name: str
    branch_role: str
    title: str
    description: str
    files: list[MRFileChange]
    file_count: int
    total_bytes: int
    warnings: list[str]
    can_submit: bool


class MRSubmitResult(_Base):
    ok: bool
    kind: str
    branch: str
    files: int
    merge_request: dict[str, Any]


# ── overview ──────────────────────────────────────────────────

class OverviewTotals(_Base):
    runs: int = 0
    running: int = 0
    failed: int = 0
    done: int = 0
    tokens: int = 0
    tool_calls: int = 0
    errors: int = 0


class OverviewResponse(_Base):
    totals: OverviewTotals
    recent: list[RunSummary]


# ── costs ────────────────────────────────────────────────────

class CostsResponse(_Base):
    by_source: dict[str, dict[str, Any]]
    by_model: dict[str, dict[str, Any]]
    model_usage: list[dict[str, Any]]
    total_input_tokens: int
    total_output_tokens: int
