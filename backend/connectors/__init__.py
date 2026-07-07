"""SCM 커넥터 계층 — GitLab·GitHub 동등 1급 (decision-scm-connector-abstraction).

파이프라인·제출·등록이 프로바이더를 모르게 하는 포트/어댑터 (concept-port-adapter).
"""
from .base import (
    ChangeRequest,
    ProjectInfo,
    ScmAuthError,
    ScmConnector,
    ScmError,
    ScmNotFoundError,
    ScmRateLimitError,
)
from .factory import connector_for_settings, connector_for_target, make_connector
from .github import GitHubConnector
from .gitlab import GitLabConnector

__all__ = [
    "ChangeRequest",
    "GitHubConnector",
    "GitLabConnector",
    "ProjectInfo",
    "ScmAuthError",
    "ScmConnector",
    "ScmError",
    "ScmNotFoundError",
    "ScmRateLimitError",
    "connector_for_settings",
    "connector_for_target",
    "make_connector",
]
