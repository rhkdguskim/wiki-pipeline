"""Requirements Collector — stakeholder intent → structured requirement.

설계: raw/2026-07-08-llm-wiki-development-pipeline-future-plan.md §3-4.
요구사항을 구조화하고, 질문을 관리하고, spec 으로 승격하는 API.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, select
from sqlalchemy.orm import Session

from .models import Base
from .api import _db, require_api_token

log = logging.getLogger("controlplane.requirements")

router = APIRouter()


# ── DB Models ────────────────────────────────────────────────

class Requirement(Base):
    __tablename__ = "requirements"
    id = Column(String(64), primary_key=True)
    source_kind = Column(String(40), nullable=False, server_default="chat")
    source_uri = Column(String(500), nullable=False, server_default="")
    status = Column(String(32), nullable=False, server_default="draft")
    problem = Column(Text, nullable=False, server_default="")
    users_json = Column(JSON, nullable=True)
    goals_json = Column(Text, nullable=True)
    non_goals_json = Column(Text, nullable=True)
    functional_reqs_json = Column(Text, nullable=True)
    non_functional_reqs_json = Column(Text, nullable=True)
    constraints_json = Column(Text, nullable=True)
    risks_json = Column(Text, nullable=True)
    dependencies_json = Column(Text, nullable=True)
    wiki_targets_json = Column(Text, nullable=True)
    dev_ticket_candidates_json = Column(Text, nullable=True)
    owner = Column(String(120), nullable=False, server_default="")
    priority = Column(String(16), nullable=False, server_default="should")
    created_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)


class RequirementQuestion(Base):
    __tablename__ = "requirement_questions"
    id = Column(String(64), primary_key=True)
    requirement_id = Column(String(64), ForeignKey("requirements.id"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    blocking = Column(String(8), nullable=False, server_default="false")
    answer = Column(Text, nullable=True)
    answered_by = Column(String(120), nullable=True)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


# ── Pydantic schemas ─────────────────────────────────────────

class RequirementIntake(BaseModel):
    raw_request: str = Field(..., min_length=1)
    source_kind: str = "chat"
    source_uri: str = ""
    owner: str = ""
    priority: str = "should"


class RequirementPatch(BaseModel):
    status: str | None = None
    owner: str | None = None
    priority: str | None = None
    problem: str | None = None


class ClarificationPayload(BaseModel):
    question_id: str = ""
    answer: str = ""


# ── helpers ──────────────────────────────────────────────────

def _to_view(row: Requirement) -> dict:
    import json
    def _parse(v):
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return v
    return {
        "id": row.id,
        "source_kind": row.source_kind,
        "source_uri": row.source_uri,
        "status": row.status,
        "problem": row.problem,
        "users": _parse(row.users_json) or [],
        "goals": _parse(row.goals_json) or [],
        "non_goals": _parse(row.non_goals_json) or [],
        "functional_requirements": _parse(row.functional_reqs_json) or [],
        "non_functional_requirements": _parse(row.non_functional_reqs_json) or [],
        "constraints": _parse(row.constraints_json) or [],
        "risks": _parse(row.risks_json) or [],
        "dependencies": _parse(row.dependencies_json) or [],
        "wiki_targets": _parse(row.wiki_targets_json) or [],
        "dev_ticket_candidates": _parse(row.dev_ticket_candidates_json) or [],
        "owner": row.owner,
        "priority": row.priority,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


# ── routes ───────────────────────────────────────────────────

@router.post("/api/requirements/intake", dependencies=[Depends(require_api_token)])
def intake_requirement(request: dict = Body(...), db: Session = Depends(_db)) -> dict:
    raw = str(request.get("raw_request") or "").strip()
    if not raw:
        raise HTTPException(400, "raw_request is required")
    rid = f"req-{uuid.uuid4().hex[:12]}"
    row = Requirement(
        id=rid,
        source_kind=str(request.get("source_kind") or "chat")[:40],
        source_uri=str(request.get("source_uri") or "")[:500],
        status="draft",
        problem=raw[:10000],
        owner=str(request.get("owner") or "")[:120],
        priority=str(request.get("priority") or "should")[:16],
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(row)
    db.flush()
    return _to_view(row)


@router.get("/api/requirements", dependencies=[Depends(require_api_token)])
def list_requirements(db: Session = Depends(_db),
                      status: str = Query("", description="filter by status"),
                      limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    stmt = select(Requirement).order_by(Requirement.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Requirement.status == status)
    return [_to_view(r) for r in db.scalars(stmt).all()]


@router.get("/api/requirements/{requirement_id}", dependencies=[Depends(require_api_token)])
def get_requirement(requirement_id: str, db: Session = Depends(_db)) -> dict:
    row = db.get(Requirement, requirement_id)
    if row is None:
        raise HTTPException(404, "requirement not found")
    view = _to_view(row)
    qs = db.scalars(
        select(RequirementQuestion)
        .where(RequirementQuestion.requirement_id == requirement_id)
        .order_by(RequirementQuestion.created_at)
    ).all()
    view["open_questions"] = [{
        "id": q.id, "question": q.question, "blocking": q.blocking == "true",
        "answer": q.answer or "", "answered_by": q.answered_by or "",
    } for q in qs if not q.answer]
    view["answered_questions"] = [{
        "id": q.id, "question": q.question, "answer": q.answer,
        "answered_by": q.answered_by,
    } for q in qs if q.answer]
    return view


@router.patch("/api/requirements/{requirement_id}", dependencies=[Depends(require_api_token)])
def patch_requirement(requirement_id: str, payload: dict = Body(...),
                      db: Session = Depends(_db)) -> dict:
    row = db.get(Requirement, requirement_id)
    if row is None:
        raise HTTPException(404, "requirement not found")
    for fld in ("status", "owner", "priority", "problem"):
        if fld in payload and payload[fld] is not None:
            setattr(row, fld, str(payload[fld])[: (5000 if fld == "problem" else 120)])
    row.updated_at = _utcnow()
    db.flush()
    return _to_view(row)


@router.post("/api/requirements/{requirement_id}/clarifications",
             dependencies=[Depends(require_api_token)])
def add_clarification(requirement_id: str, payload: dict = Body(...),
                      db: Session = Depends(_db)) -> dict:
    row = db.get(Requirement, requirement_id)
    if row is None:
        raise HTTPException(404, "requirement not found")
    qid = str(payload.get("question_id") or f"q-{uuid.uuid4().hex[:8]}")
    answer = str(payload.get("answer") or "").strip()
    is_blocking = str(payload.get("blocking") or "false") == "true"
    if answer:
        existing = db.get(RequirementQuestion, qid)
        if existing and existing.requirement_id == requirement_id:
            existing.answer = answer[:5000]
            existing.answered_by = str(payload.get("answered_by") or "user")[:120]
            existing.answered_at = _utcnow()
        else:
            db.add(RequirementQuestion(
                id=qid, requirement_id=requirement_id,
                question=str(payload.get("question") or "")[:2000],
                blocking=("true" if is_blocking else "false")[:8],
                answer=answer[:5000],
                answered_by=str(payload.get("answered_by") or "user")[:120],
                answered_at=_utcnow(),
                created_at=_utcnow(),
            ))
    else:
        db.add(RequirementQuestion(
            id=qid, requirement_id=requirement_id,
            question=str(payload.get("question") or "")[:2000],
            blocking=("true" if is_blocking else "false")[:8],
            created_at=_utcnow(),
        ))
    blocking_open = db.scalars(
        select(RequirementQuestion).where(
            RequirementQuestion.requirement_id == requirement_id,
            RequirementQuestion.answer.is_(None),
            RequirementQuestion.blocking == "true",
        )
    ).first()
    if blocking_open and is_blocking and row.status == "draft":
        row.status = "needs_clarification"
    elif not blocking_open and row.status in ("draft", "needs_clarification"):
        row.status = "ready_for_spec"
    row.updated_at = _utcnow()
    db.flush()
    return get_requirement(requirement_id, db)


@router.post("/api/requirements/{requirement_id}/promote-to-spec",
             dependencies=[Depends(require_api_token)])
def promote_to_spec(requirement_id: str, db: Session = Depends(_db)) -> dict:
    row = db.get(Requirement, requirement_id)
    if row is None:
        raise HTTPException(404, "requirement not found")
    blocking = db.scalars(
        select(RequirementQuestion).where(
            RequirementQuestion.requirement_id == requirement_id,
            RequirementQuestion.answer.is_(None),
            RequirementQuestion.blocking == "true",
        )
    ).first()
    if blocking:
        raise HTTPException(409, f"blocking question unanswered: {blocking.id}")
    if row.status not in ("draft", "needs_clarification", "ready_for_spec"):
        raise HTTPException(409, f"cannot promote from status: {row.status}")
    row.status = "promoted_to_spec"
    row.updated_at = _utcnow()
    db.flush()
    return {"ok": True, "requirement_id": requirement_id, "status": "promoted_to_spec"}
