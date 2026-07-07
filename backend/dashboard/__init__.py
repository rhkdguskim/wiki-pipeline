"""관측 대시보드 — events-*.jsonl(progress.v1)을 실시간 소비하는 피드백 I/F.

observer.py가 이벤트마다 flush하는 JSONL을 서버(serve.py)가 바이트 오프셋으로
증분 tail하고, 브라우저(index.html)가 폴링해 4단 계층 진행·토큰 사용량·경과
시간을 렌더한다. 이벤트 스키마 계약은 common/events.py(progress.v1)가 단일
기준이다 (decision-observability-event-contract) — 이 패키지는 소비자일 뿐
스키마를 정의하지 않는다.
"""
