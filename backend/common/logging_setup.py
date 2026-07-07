"""구조화 로깅 초기화 — LOG_LEVEL(.env)을 실제로 반영한다.

파이프라인 진행 상황은 Observer(이벤트 계약)가 담당하고, 이 로거는 시스템 내부
진단(서버·스케줄러·러너·알림)용이다. 모든 엔트리포인트가 기동 시 1회 호출한다.
"""
from __future__ import annotations

import logging

from .config import cached_settings

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"


def setup_logging(level: str | None = None) -> None:
    resolved = (level or cached_settings().log_level or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format=_FORMAT,
        force=False,   # 이미 구성돼 있으면 존중 (테스트 러너 등)
    )
    # 폴링·헬스체크로 시끄러운 액세스 로그는 한 단계 조용히.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
