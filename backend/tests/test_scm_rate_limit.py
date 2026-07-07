"""SCM rate-limit(403/429) 오분류 회귀 테스트 (decision-scm-rate-limit-not-auth).

GitHub/GitLab의 API rate limit 응답은 401/403 대역과 겹치지만 토큰은 유효하다 —
ScmAuthError(auth_revoked 알림·잠재적 오탐)가 아니라 ScmRateLimitError로 분류돼야 한다.
"""
from __future__ import annotations

import httpx
import pytest

from backend.connectors.base import ScmAuthError, ScmRateLimitError
from backend.connectors.github import _wrap_http_error as github_wrap
from backend.connectors.gitlab import _wrap_http_error as gitlab_wrap


def _status_error(resp: httpx.Response) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.example.com/repos/x/y")
    resp.request = request
    return httpx.HTTPStatusError("boom", request=request, response=resp)


def test_github_rate_limit_403_with_remaining_zero_header():
    body = ('{"message":"API rate limit exceeded for 1.2.3.4.",'
            '"documentation_url":"https://docs.github.com/rest"}')
    resp = httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, text=body)
    err = github_wrap(_status_error(resp))
    assert isinstance(err, ScmRateLimitError)
    assert not isinstance(err, ScmAuthError)


def test_github_rate_limit_detected_from_message_body_without_headers():
    body = '{"message":"API rate limit exceeded for 123.141.48.166."}'
    resp = httpx.Response(403, text=body)
    err = github_wrap(_status_error(resp))
    assert isinstance(err, ScmRateLimitError)


def test_github_secondary_rate_limit_429():
    resp = httpx.Response(429, text='{"message":"secondary rate limit"}')
    err = github_wrap(_status_error(resp))
    assert isinstance(err, ScmRateLimitError)


def test_github_real_auth_failure_is_not_rate_limited():
    resp = httpx.Response(403, text='{"message":"Bad credentials"}')
    err = github_wrap(_status_error(resp))
    assert isinstance(err, ScmAuthError)
    assert not isinstance(err, ScmRateLimitError)


def test_github_401_is_always_auth():
    resp = httpx.Response(401, text='{"message":"Bad credentials"}')
    err = github_wrap(_status_error(resp))
    assert isinstance(err, ScmAuthError)


def test_gitlab_rate_limit_429():
    resp = httpx.Response(429, text="Retry later")
    err = gitlab_wrap(_status_error(resp))
    assert isinstance(err, ScmRateLimitError)


def test_gitlab_rate_limit_remaining_zero_header():
    resp = httpx.Response(403, headers={"ratelimit-remaining": "0"}, text="")
    err = gitlab_wrap(_status_error(resp))
    assert isinstance(err, ScmRateLimitError)


def test_gitlab_real_auth_failure_is_not_rate_limited():
    resp = httpx.Response(403, text="403 Forbidden")
    err = gitlab_wrap(_status_error(resp))
    assert isinstance(err, ScmAuthError)
    assert not isinstance(err, ScmRateLimitError)
