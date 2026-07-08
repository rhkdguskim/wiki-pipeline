"""ScmConnector 포트 — 커넥터 3책임(compare·submit·auth) + 파이프라인 읽기 도구 계약.

정규화 규약 (모든 구현이 동일한 dict 형태를 반환한다):
- compare()   -> [{"new_path", "old_path", "new_file", "deleted_file", "renamed_file"}]
- list_tree() / list_tree_all() -> [{"path", "name", "type"}]  (type: "blob" | "tree")
- resolve_ref() -> 40자 전체 커밋 sha (상태 포인터는 항상 전체 sha — concept-idempotent-sha)
- change request = GitLab MR / GitHub PR의 통합 개념. 열린 자동 MR 갱신 규칙
  (decision-mr-review-gate)을 위해 find/create/update를 분리해 노출한다.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


class ScmError(RuntimeError):
    """커넥터 공통 예외 — 프로바이더 원본 예외를 감싼다."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ScmNotFoundError(ScmError):
    """404 — 레포/브랜치/파일 소실. 소스 자동 비활성화 판정에 쓰인다 (decision-branch-loss-policy)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class ScmAuthError(ScmError):
    """401/403 — 토큰 무효·권한 부족. admin 알림 대상 (decision-engine-api-key-auth 준용)."""


class ScmRateLimitError(ScmError):
    """403/429 API rate limit — 토큰은 유효하다. 일시적 오류이므로 auth 알림/자동 비활성화 대상이
    아니다 (decision-scm-rate-limit-not-auth). run은 실패로 기록되되 재시도 시 자연 복구된다."""


@dataclass(frozen=True)
class ProjectInfo:
    """verify_access()·project_info()의 결과 — 등록 자동 조회에 사용."""

    name: str
    default_branch: str
    namespace_path: str        # gitlab: full path, github: "owner/repo"
    web_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ChangeRequest:
    """MR/PR 통합 표현."""

    id: str                    # gitlab: iid, github: number (프로바이더 내 식별자)
    web_url: str
    state: str
    title: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TagRef:
    """태그 참조 — 매뉴얼 파이프라인 트리거(decision-release-tag-trigger) 폴링용.

    name: 태그명(예: v1.2.3, release-2026-07-08).
    sha: 태그가 가리키는 커밋(40자). annotated tag 라면 태그 객체 자체 sha 가 아니라
         그 태그가 가리키는 커밋 sha 를 반환한다 (상태 비교 일관성).
    target_branch: 태그가 찍힌 브랜치(추정). GitLab/GitHub API 모두 직접 제공하지 않으므로
                   커넥터 구현이 판단한다 (보통 default_branch 또는 release 전용 브랜치).
    """

    name: str
    sha: str
    target_branch: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


class ScmConnector(abc.ABC):
    """프로바이더 중립 SCM 계약. 모든 메서드는 동기·멱등 재시도 내장(읽기 한정)."""

    kind: str = ""

    # ── read (파이프라인 탐색·변경 감지) ─────────────────────────
    @abc.abstractmethod
    def compare(self, from_sha: str, to_sha: str) -> list[dict]: ...

    @abc.abstractmethod
    def raw_file(self, path: str, ref: str) -> str: ...

    @abc.abstractmethod
    def list_tree(self, path: str = "", ref: str = "HEAD") -> list[dict]: ...

    @abc.abstractmethod
    def list_tree_all(self, ref: str = "HEAD", recursive: bool = True) -> list[dict]: ...

    @abc.abstractmethod
    def resolve_ref(self, ref: str) -> str: ...

    @abc.abstractmethod
    def default_branch(self) -> str: ...

    @abc.abstractmethod
    def list_branches(self) -> list[str]: ...

    def list_tags(self) -> list[TagRef]:
        """릴리스 태그 목록 (최신순). 매뉴얼 파이프라인 트리거 폴링이 쓴다.

        v1: 기본 구현은 빈 목록(미지원 커넥터 호환). GitLab·GitHub 구현이 덮어쓴다.
        폴링 사이드이펙트 최소화를 위해 최신 N(기본 50)개만 반환한다.
        """
        return []

    @abc.abstractmethod
    def project_info(self) -> ProjectInfo: ...

    def project_name(self) -> str:
        return self.project_info().name

    # ── auth (등록 dry-run 검증) ────────────────────────────────
    def verify_access(self) -> ProjectInfo:
        """토큰·프로젝트 접근을 검증하고 자동 조회 정보를 돌려준다 (등록 플로우)."""
        info = self.project_info()
        self.resolve_ref(info.default_branch)
        return info

    # ── write (docs-hub / 산출물 제출) ──────────────────────────
    @abc.abstractmethod
    def ensure_branch(self, branch: str, ref: str) -> dict: ...

    @abc.abstractmethod
    def upsert_file(self, *, branch: str, path: str, content: str, message: str) -> dict: ...

    @abc.abstractmethod
    def find_open_change_request(self, *, source_branch: str, target_branch: str) -> ChangeRequest | None: ...

    @abc.abstractmethod
    def create_change_request(self, *, source_branch: str, target_branch: str,
                              title: str, description: str) -> ChangeRequest: ...

    @abc.abstractmethod
    def update_change_request(self, cr_id: str, *, title: str, description: str) -> ChangeRequest: ...

    def create_or_update_change_request(self, *, source_branch: str, target_branch: str,
                                        title: str, description: str) -> ChangeRequest:
        """열린 자동 MR/PR이 있으면 갱신, 없으면 생성 (decision-mr-review-gate 중복 방지)."""
        existing = self.find_open_change_request(
            source_branch=source_branch, target_branch=target_branch)
        if existing is not None:
            return self.update_change_request(existing.id, title=title, description=description)
        return self.create_change_request(
            source_branch=source_branch, target_branch=target_branch,
            title=title, description=description)

    @abc.abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> "ScmConnector":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
