"""Prometheus 메트릭 — /metrics 엔드포인트로 노출.

수집 메트릭:
- http_requests_total{method,path,status} — API 카운터
- http_request_duration_seconds{method,path} — 히스토그램
- http_requests_in_flight — 게이지
- run_pipeline_runs_total{pipeline,status} — 파이프라인 종료 카운터
- run_pipeline_duration_seconds{pipeline} — 파이프라인 실행 시간
- run_pipeline_tokens_total{pipeline,kind} — 토큰 사용량
- run_webhook_events_total — 런너→CP webhook 수신
- run_mr_submissions_total{outcome} — MR 제출 결과

메트릭 이름은 Prometheus 컨벤션(https://prometheus.io/docs/practices/naming/)
을 따른다. 라벨 cardinality 는 path/소스가 폭증하지 않도록 정규화한다.
"""
from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


# ── 글로벌 (default) 레지스트리. 테스트 시 reset 가능 ──────────────
REGISTRY = CollectorRegistry(auto_describe=True)


# HTTP 계측 — path 는 route template 으로 정규화 (cardinality 보호)
http_requests_total = Counter(
    "wiki_pipeline_http_requests_total",
    "HTTP requests served by the Control Plane.",
    labelnames=("method", "path", "status"),
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "wiki_pipeline_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

http_requests_in_flight = Gauge(
    "wiki_pipeline_http_requests_in_flight",
    "Currently in-flight HTTP requests.",
    registry=REGISTRY,
)


# 파이프라인 계측 — /api/runs/trigger 와 /api/webhook/complete 에서 emit
run_pipeline_runs_total = Counter(
    "wiki_pipeline_run_pipeline_runs_total",
    "Pipeline runs by pipeline_id and final status.",
    labelnames=("pipeline_id", "status"),
    registry=REGISTRY,
)

run_pipeline_duration_seconds = Histogram(
    "wiki_pipeline_run_pipeline_duration_seconds",
    "Pipeline run wall-clock duration in seconds.",
    labelnames=("pipeline_id",),
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
    registry=REGISTRY,
)

run_pipeline_tokens_total = Counter(
    "wiki_pipeline_run_pipeline_tokens_total",
    "Token usage accumulated by pipeline and direction (input|output).",
    labelnames=("pipeline_id", "direction"),
    registry=REGISTRY,
)

run_webhook_events_total = Counter(
    "wiki_pipeline_run_webhook_events_total",
    "Runner->Control Plane webhook events received.",
    registry=REGISTRY,
)

run_mr_submissions_total = Counter(
    "wiki_pipeline_run_mr_submissions_total",
    "MR/PR submission outcomes.",
    labelnames=("outcome",),
    registry=REGISTRY,
)

# 인프라 — 정기 점검 결과 노출
infra_db_up = Gauge(
    "wiki_pipeline_infra_db_up",
    "1 if Control Plane DB connection is healthy, else 0.",
    registry=REGISTRY,
)

infra_scheduler_jobs = Gauge(
    "wiki_pipeline_infra_scheduler_jobs",
    "Number of active APScheduler jobs.",
    registry=REGISTRY,
)


# ── 헬퍼 — record_*() 함수로 호출자 코드 단순화 ─────────────────────

def record_run_completion(pipeline_id: str, status: str, duration_sec: float | None = None,
                          input_tokens: int = 0, output_tokens: int = 0) -> None:
    """run 종료 보고 시 호출. status: done|failed."""
    run_pipeline_runs_total.labels(pipeline_id=pipeline_id or "unknown",
                                   status=status or "unknown").inc()
    if duration_sec is not None and duration_sec > 0:
        run_pipeline_duration_seconds.labels(pipeline_id=pipeline_id or "unknown").observe(
            duration_sec)
    if input_tokens:
        run_pipeline_tokens_total.labels(pipeline_id=pipeline_id or "unknown",
                                          direction="input").inc(input_tokens)
    if output_tokens:
        run_pipeline_tokens_total.labels(pipeline_id=pipeline_id or "unknown",
                                          direction="output").inc(output_tokens)


def render_metrics() -> tuple[bytes, str]:
    """Prometheus text exposition format 으로 직렬화."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
