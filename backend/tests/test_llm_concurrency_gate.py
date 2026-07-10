"""LLM concurrency 게이트 + 429 재시도 강화 회귀 테스트.

Z.AI(GLM)처럼 concurrency가 낮은 공급자에서 병렬 map/reduce가 429로 전멸하던 문제의
방어선을 고정한다:
  1) llm_gate — in-flight LLM 호출 수를 한도 이하로 강제 (1차 방어).
  2) retry — 429 Retry-After 존중 + jitter로 재돌진 완화 (2차 방어).
  3) settings service — DB 설정(llm.max_concurrency)이 runner env로 주입.
"""
from __future__ import annotations

import os
import threading
import time

from backend.common import llm_gate, retry


# ── 1) 게이트: in-flight 호출 수를 한도 이하로 강제 ──────────────────────


def test_gate_caps_inflight_calls(monkeypatch):
    # 비-Z.AI provider 명시 — .env 폴백이 z.ai면 is_zai_runtime()이 1로 강제하므로.
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "3")
    llm_gate.reset_for_test()
    assert llm_gate.current_limit() == 3

    state = {"cur": 0, "max": 0}
    lock = threading.Lock()

    def worker():
        with llm_gate.llm_slot():
            with lock:
                state["cur"] += 1
                state["max"] = max(state["max"], state["cur"])
            time.sleep(0.02)
            with lock:
                state["cur"] -= 1

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert state["max"] <= 3, f"in-flight {state['max']} exceeded limit 3"


def test_gate_unlimited_when_zero(monkeypatch):
    # 비-Z.AI provider 명시 — .env 폴백이 z.ai면 is_zai_runtime()이 1로 강제하므로.
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "0")
    llm_gate.reset_for_test()
    assert llm_gate.current_limit() == 0
    # 무제한이면 슬롯 진입이 즉시 통과해야 한다 (블록 없음).
    with llm_gate.llm_slot():
        pass


def test_zai_runtime_forces_serial_gate_and_parallel_workers(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.z.ai/api/paas/v4")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "6")
    llm_gate.reset_for_test()

    assert llm_gate.is_zai_runtime() is True
    assert llm_gate.current_limit() == 1
    assert llm_gate.effective_parallelism(6) == 1


def test_gate_releases_slot_on_exception(monkeypatch):
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    llm_gate.reset_for_test()

    class Boom(Exception):
        pass

    try:
        with llm_gate.llm_slot():
            raise Boom()
    except Boom:
        pass
    # 예외로 나가도 슬롯이 반납돼 다음 진입이 블록되지 않아야 한다.
    acquired = []

    def take():
        with llm_gate.llm_slot():
            acquired.append(True)

    t = threading.Thread(target=take)
    t.start()
    t.join(timeout=2.0)
    assert acquired == [True], "슬롯이 예외 후 반납되지 않아 데드락"


# ── 2) retry: 429 Retry-After 존중 + jitter ─────────────────────────────


class _FakeResp:
    def __init__(self, headers):
        self.headers = headers


class _RateLimited(Exception):
    def __init__(self, retry_after=None, status=429):
        super().__init__("rate limited")
        self.status_code = status
        headers = {}
        if retry_after is not None:
            headers["retry-after"] = str(retry_after)
        self.response = _FakeResp(headers)


def test_429_is_transient():
    assert retry.is_transient(_RateLimited(retry_after=1))
    # 4xx(429 외)은 일시 오류가 아니다.
    assert not retry.is_transient(_RateLimited(status=400))


def test_retry_after_header_parsed():
    assert retry._retry_after_seconds(_RateLimited(retry_after=5)) == 5.0
    # 헤더 없으면 None (표준 백오프 폴백).
    assert retry._retry_after_seconds(_RateLimited(retry_after=None)) is None


def test_retry_after_capped():
    # 비현실적으로 큰 값은 상한으로 눌린다.
    assert retry._retry_after_seconds(_RateLimited(retry_after=99999)) == retry._RETRY_AFTER_MAX


def test_with_retry_eventually_succeeds_on_transient():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _RateLimited(retry_after=0)  # 0초 → 지수백오프 base로 폴백, 곧 성공
        return "ok"

    assert retry.with_retry(fn, attempts=3) == "ok"
    assert calls["n"] == 2


def test_with_retry_reraises_non_transient():
    def fn():
        raise ValueError("permanent")

    try:
        retry.with_retry(fn, attempts=3)
        assert False, "재시도 대상이 아닌 오류는 즉시 전파돼야 한다"
    except ValueError:
        pass


# ── 3) DB 설정 → runner env 주입 ────────────────────────────────────────


def test_settings_service_concurrency_roundtrip():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.controlplane.models import Base
    from backend.controlplane.services.settings import SettingsService

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    SF = sessionmaker(bind=eng)
    svc = SettingsService(SF)

    env = {
        "LLM_MAX_CONCURRENCY": "0", "LLM_PROVIDER": "openai-compatible",
        "LLM_MODEL": "glm", "LLM_API_KEY": "k", "LLM_BASE_URL": "",
        "LLM_MAX_TOKENS": "32768", "LLM_TEMPERATURE": "0.2",
        "LLM_TIMEOUT": "180", "LLM_RETRY_ATTEMPTS": "4",
    }
    with SF() as db:
        # 기본값(env) = 0.
        assert svc.get_llm_effective(db, env)["max_concurrency"] == 0
        # DB에 3 저장.
        svc.set_llm(db, {"max_concurrency": 3}, actor="test")
        db.commit()
        assert svc.get_llm_effective(db, env)["max_concurrency"] == 3
        # runner env로 문자열 주입.
        assert svc.get_llm_runtime_env(db, env)["LLM_MAX_CONCURRENCY"] == "3"
