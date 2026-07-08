"""Requirements Collector API — raw/2026-07-08-llm-wiki-development-pipeline-future-plan §3-4."""
from __future__ import annotations

import pytest

from backend.controlplane.app import create_app
from backend.controlplane.models import Base
from backend.controlplane.requirements_api import Requirement, RequirementQuestion


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_url = f"sqlite:///{tmp_path}/test-requirements.sqlite"
    monkeypatch.setenv("CONTROL_DB_URL", db_url)
    monkeypatch.setenv("CONTROL_API_TOKENS", "test:secret-test-token-value")
    monkeypatch.setenv("CONTROL_SECRET_KEY", "mhJknG_cMcqpI5stExKs4IkRyUDAztepql4YOKmlOUQ=")
    app = create_app()
    from sqlalchemy import create_engine
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Requirement.__table__.create(engine, checkfirst=True)
    RequirementQuestion.__table__.create(engine, checkfirst=True)
    from fastapi.testclient import TestClient
    return TestClient(app), app


def _headers():
    return {"X-Api-Token": "secret-test-token-value"}


def test_intake_requirement(client):
    c, _app = client
    r = c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "사용자가 매뉴얼 페이지에서 검색을 빠르게 할 수 있어야 한다",
        "source_kind": "chat",
        "owner": "frontend-team",
        "priority": "should",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"].startswith("req-")
    assert data["status"] == "draft"
    assert data["problem"].startswith("사용자가")
    assert data["owner"] == "frontend-team"
    assert data["priority"] == "should"


def test_intake_requires_raw_request(client):
    c, _app = client
    r = c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "",
    })
    assert r.status_code == 400


def test_list_requirements(client):
    c, _app = client
    c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "요구사항 1", "priority": "must",
    })
    c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "요구사항 2", "priority": "should",
    })
    r = c.get("/api/requirements", headers=_headers())
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 2
    c.get("/api/requirements", headers=_headers(), params={"status": "draft"})


def test_get_requirement_with_questions(client):
    c, _app = client
    intake = c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "A/B 테스트 인프라가 필요하다",
    }).json()
    rid = intake["id"]
    c.post(f"/api/requirements/{rid}/clarifications", headers=_headers(), json={
        "question": "테스트 대상 페이지는?",
        "blocking": "true",
    })
    r = c.get(f"/api/requirements/{rid}", headers=_headers())
    assert r.status_code == 200
    data = r.json()
    assert len(data["open_questions"]) == 1
    assert data["open_questions"][0]["question"] == "테스트 대상 페이지는?"
    assert data["open_questions"][0]["blocking"] is True
    assert data["status"] == "needs_clarification"


def test_answer_clears_blocking_and_promotes_status(client):
    c, _app = client
    intake = c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "조건부 로직이 분기마다 다른 결과를 반환해야 한다",
    }).json()
    rid = intake["id"]
    q = c.post(f"/api/requirements/{rid}/clarifications", headers=_headers(), json={
        "question": "분기 종류는?", "blocking": "true",
    }).json()
    qid = q["open_questions"][0]["id"]
    c.post(f"/api/requirements/{rid}/clarifications", headers=_headers(), json={
        "question_id": qid, "answer": "A/B/C 3개", "answered_by": "user",
    })
    data = c.get(f"/api/requirements/{rid}", headers=_headers()).json()
    assert data["status"] == "ready_for_spec"
    assert len(data["open_questions"]) == 0
    assert len(data["answered_questions"]) == 1


def test_promote_to_spec_blocked_by_unanswered_question(client):
    c, _app = client
    intake = c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "기능 X 가 필요하다",
    }).json()
    rid = intake["id"]
    c.post(f"/api/requirements/{rid}/clarifications", headers=_headers(), json={
        "question": "누가 쓰는지?", "blocking": "true",
    })
    c.patch(f"/api/requirements/{rid}", headers=_headers(), json={"status": "ready_for_spec"})
    r = c.post(f"/api/requirements/{rid}/promote-to-spec", headers=_headers())
    assert r.status_code == 409


def test_promote_to_spec_success(client):
    c, _app = client
    intake = c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "지원 매뉴얼 라이트/다크 토글",
    }).json()
    rid = intake["id"]
    r = c.post(f"/api/requirements/{rid}/promote-to-spec", headers=_headers())
    assert r.status_code == 200
    assert r.json()["status"] == "promoted_to_spec"


def test_patch_requirement(client):
    c, _app = client
    intake = c.post("/api/requirements/intake", headers=_headers(), json={
        "raw_request": "초기 요구사항",
    }).json()
    rid = intake["id"]
    r = c.patch(f"/api/requirements/{rid}", headers=_headers(), json={
        "priority": "must", "owner": "qa-team",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["priority"] == "must"
    assert data["owner"] == "qa-team"


def test_get_nonexistent_requirement_returns_404(client):
    c, _app = client
    r = c.get("/api/requirements/req-does-not-exist", headers=_headers())
    assert r.status_code == 404


def test_unauthenticated_request_rejected(client):
    c, _app = client
    r = c.post("/api/requirements/intake", json={"raw_request": "test"})
    assert r.status_code == 401
