"""Control Plane — 관리 서버 (FastAPI + SQLAlchemy).

decision-control-plane-fastapi · decision-control-plane-postgresql ·
decision-db-source-of-truth · decision-server-vm-self-token.

역할: 소스/인스턴스/타깃 등록(자동 조회 + dry-run 검증), 과제별 스케줄·수동 트리거,
러너 webhook 이벤트 수신·적재, 대시보드 API, 역할 기반 이메일 알림.
"""
