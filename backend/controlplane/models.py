"""Control Plane 스키마 (decision-db-source-of-truth + decision-scm-multi-instance-github-mvp).

소스 등록의 단위 = "SCM 인스턴스 × 레포": scm_instances가 엔드포인트·토큰을,
sources가 레포·테마·스케줄을, source_branches가 역할(dev/release)별 sha 포인터를 가진다.
이력(runs·run_items·run_events)은 비활성화 후에도 삭제하지 않는다 (감사·재처리).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ScmInstance(Base):
    """SCM 인스턴스 — 사내 GitLab · gitlab.com · github.com 등."""

    __tablename__ = "scm_instances"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))            # gitlab | github
    label: Mapped[str] = mapped_column(String(200), default="")
    base_url: Mapped[str] = mapped_column(String(500), default="")   # github.com은 빈 값 허용
    token: Mapped[str] = mapped_column(Text, default="")             # SecretBox로 암호화 저장
    token_header: Mapped[str] = mapped_column(String(40), default="PRIVATE-TOKEN")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Track B-1: 토큰 마지막 순환 시각. 시크릿은 저장하지 않고 시점만.
    # 1차 마이그레이션은 0002 에서 추가. 기존 row 는 NULL — "모름" 으로 간주.
    token_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sources: Mapped[list["Source"]] = relationship(back_populates="instance")
    token_rotations: Mapped[list["ScmInstanceTokenRotation"]] = relationship(
        back_populates="instance",
        order_by="ScmInstanceTokenRotation.rotated_at.desc()",
    )


class Source(Base):
    """문서화 대상 레포 1건."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("scm_instances.id"))
    label: Mapped[str] = mapped_column(String(200), default="")
    repo: Mapped[str] = mapped_column(String(300))           # gitlab: project id/path, github: owner/repo
    # 레포별 토큰(project access token) — 인스턴스 토큰보다 우선 (decision-repo-dev-release-registration)
    token: Mapped[str] = mapped_column(Text, default="")
    doc_dir: Mapped[str] = mapped_column(String(300), default="")   # docs-hub 폴더 (자동: namespace_path)
    themes: Mapped[str] = mapped_column(String(500), default="")
    owner_email: Mapped[str] = mapped_column(String(200), default="")   # 과제 담당자 (알림 수신)
    schedule_cron: Mapped[str] = mapped_column(String(100), default="")  # 비우면 서버 기본값
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    disabled_reason: Mapped[str] = mapped_column(String(300), default="")  # 좀비 소스 자동 비활성화 사유
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    instance: Mapped[ScmInstance] = relationship(back_populates="sources")
    branches: Mapped[list["SourceBranch"]] = relationship(back_populates="source")
    schedules: Mapped[list["SourceSchedule"]] = relationship(back_populates="source")


class SourceBranch(Base):
    """역할(dev|release)별 브랜치 + sha 포인터 (concept-idempotent-sha)."""

    __tablename__ = "source_branches"
    __table_args__ = (UniqueConstraint("source_id", "role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    role: Mapped[str] = mapped_column(String(16))            # dev | release
    branch: Mapped[str] = mapped_column(String(200), default="")
    baseline_sha: Mapped[str] = mapped_column(String(64), default="")
    last_processed_sha: Mapped[str] = mapped_column(String(64), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped[Source] = relationship(back_populates="branches")


class SourceSchedule(Base):
    """저장소별 자동 실행 스케줄. 한 source에 여러 파이프라인 스케줄을 둘 수 있다."""

    __tablename__ = "source_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    pipeline_id: Mapped[str] = mapped_column(String(32), default="static")
    mode: Mapped[str] = mapped_column(String(16), default="auto")
    branch_role: Mapped[str] = mapped_column(String(16), default="dev")
    cron: Mapped[str] = mapped_column(String(100), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped[Source] = relationship(back_populates="schedules")


class Run(Base):
    """파이프라인 실행 1건 — Data Plane 러너가 webhook으로 상태를 갱신한다."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)   # run_id
    source_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    pipeline_id: Mapped[str] = mapped_column(String(32), default="")  # static | manual
    mode: Mapped[str] = mapped_column(String(16), default="")         # init | diff | manual
    branch_role: Mapped[str] = mapped_column(String(16), default="dev")
    trigger: Mapped[str] = mapped_column(String(16), default="manual")  # manual | schedule
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|done|failed
    from_sha: Mapped[str] = mapped_column(String(64), default="")
    to_sha: Mapped[str] = mapped_column(String(64), default="")
    doc_count: Mapped[int] = mapped_column(Integer, default=0)
    mr_url: Mapped[str] = mapped_column(String(500), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RunEvent(Base):
    """진행 이벤트 (decision-observability-event-contract) — id가 증분 폴링 커서."""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(120), index=True)
    ts: Mapped[str] = mapped_column(String(40), default="")
    layer: Mapped[str] = mapped_column(String(20), default="")
    stage: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16), default="")
    payload: Mapped[str] = mapped_column(Text, default="{}")   # 원본 이벤트 JSON


class RunModelUsage(Base):
    """모델별 토큰 사용량 — run_events 보존 정책과 별도로 장기 집계한다."""

    __tablename__ = "run_model_usage"
    __table_args__ = (UniqueConstraint("run_id", "provider", "model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(120), index=True)
    source_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    pipeline_id: Mapped[str] = mapped_column(String(32), default="")
    provider: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DocTarget(Base):
    """docs-hub 제출 대상 (product-common 등)."""

    __tablename__ = "doc_targets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(16), default="gitlab")
    url: Mapped[str] = mapped_column(String(500), default="")
    project_id: Mapped[str] = mapped_column(String(100), default="")
    project_path: Mapped[str] = mapped_column(String(300), default="")
    token: Mapped[str] = mapped_column(Text, default="")       # SecretBox로 암호화 저장
    token_header: Mapped[str] = mapped_column(String(40), default="PRIVATE-TOKEN")
    default_branch: Mapped[str] = mapped_column(String(100), default="master")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SourceReleaseTag(Base):
    """매뉴얼 파이프라인 태그 폴링 북마크 — source × 역할별 마지막으로 본 태그.

    decision-release-tag-trigger: 릴리스/버전 태그가 매뉴얼 파이프라인을 트리거.
    폴링이 같은 태그로 run을 중복 생성하지 않도록 마지막으로 관측한 태그 이름을 저장한다.
    run 성공 여부와 무관하게 '이 태그까지 봤다'를 기록 — 재시도는 사용자 수동 트리거로.
    """

    __tablename__ = "source_release_tags"
    __table_args__ = (UniqueConstraint("source_id", "branch_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    branch_role: Mapped[str] = mapped_column(String(16), default="release")
    last_seen_tag: Mapped[str] = mapped_column(String(200), default="")
    last_seen_sha: Mapped[str] = mapped_column(String(64), default="")
    last_run_id: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ScmInstanceTokenRotation(Base):
    """SCM 인스턴스 토큰 순환 이력 (question-cloud-scm-token-policy 운영 답변).

    token_rotated_at: 마지막으로 토큰이 등록/갱신된 시각. 시크릿은 평문 미저장 — 시점만.
    rotated_by_token: 갱신 당시의 API 토큰 이름(추적용, 평문 비밀 X).
    note: 사유 (예: "first registration", "scheduled rotation", "auth_revoked").
    """

    __tablename__ = "scm_instance_token_rotations"
    __table_args__ = (UniqueConstraint("instance_id", "rotated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("scm_instances.id"), index=True)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    rotated_by_token: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(String(200), default="")

    instance: Mapped["ScmInstance"] = relationship(back_populates="token_rotations")


class AuditLog(Base):
    """관리 작업 감사 추적 (ENT-F). run_events 와 별개로 영구 보존한다.

    어떤 토큰(누가)이 어떤 action 을 어떤 대상에 했는지. 비밀 값은 저장하지 않는다.
    인덱스: ts DESC(최근), (action, ts) — action 별 시간대 조회, (actor, ts) — 사람별.
    보존: audit_log_retention_days. 0 이면 영구.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(120), default="", index=True)
    action: Mapped[str] = mapped_column(String(80), default="", index=True)
    target_kind: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    request_id: Mapped[str] = mapped_column(String(40), default="")
    detail: Mapped[str] = mapped_column(Text, default="")   # JSON payload (secrets 포함 금지)
    remote_addr: Mapped[str] = mapped_column(String(64), default="")


class SystemSetting(Base):
    """시스템 설정 키-값 저장 (ENT-F 후속 · LLM Settings).

    .env 의존을 줄이고 운영 중 대시보드에서 변경 가능하게 한다. key 가 "namespace.field"
    형식 (예: "llm.provider", "llm.api_key") 이고 value 는 문자열로 직렬화.
    비밀 값(API key 등) 도 평문 저장 — 운영에서는 Fernet 암호화 컬럼 또는
    SecretBox 적용이 이상이나 v1 은 .env 대체 수단으로 평문 저장 (SecretBox 와 별도
    컨텍스트로 격리).
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str] = mapped_column(String(120), default="")
