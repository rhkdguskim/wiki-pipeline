"""파이프라인 공통 계층 — 두 파이프라인이 공유하는 재사용 에이전트·오케스트레이션 패턴.

계층 규칙: common(저수준 런타임) <- common_pipeline(이 패키지) <- 각 파이프라인.
common_pipeline은 common만 알고 파이프라인은 모른다 — 파이프라인 고유 지식
(프롬프트·도구·테마 데이터·근거 소스)은 전부 콜러블/데이터로 주입받는다.

  - run_context : 러너 스캐폴드 (run_id·observer·run 계층 이벤트·자원 정리)
  - writer      : writer 에이전트 실행 패턴 (수정모드 프롬프트 합성 + 1회 실행)
  - verify      : write -> 형식검증 -> lint -> critic -> 재시도 루프 (경고태그 정책)
  - parallel    : 에이전트 병렬 분배 (완료 순서 스트리밍)
  - theme       : 테마 계약 (ThemeSpec·brief) — 레지스트리 데이터는 파이프라인 소유
  - output      : 생성 문서 저장 (strip_reasoning + .md)
"""
