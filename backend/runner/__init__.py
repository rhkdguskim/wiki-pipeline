"""Data Plane 러너 — Control Plane 트리거로 파이프라인을 실행하고 결과를 보고한다.

decision-control-data-plane-split: 러너는 실행만 담당. 컨텍스트(소스·토큰·sha)는
Control Plane에서 받고, 이벤트는 webhook으로 push하며(로컬 JSONL은 감사 사본),
완료 보고가 sha 전진의 유일한 경로다 (concept-idempotent-sha).
"""
