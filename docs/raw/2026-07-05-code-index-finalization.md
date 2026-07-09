# 코드 인덱스 파이프라인 최종 확정 — 어댑터·질의 범위·저장소 평면 (2026-07-05)

> 코드 인덱스 파이프라인 설계의 마지막 열린 질문 3건에 대한 사용자 결정 기록.
> 직전 논의([[2026-07-05-code-index-pipeline]] · [[2026-07-05-code-index-followup]])에서 확정된
> 사항(MCP 서빙·러너 git clone·버전 스냅샷 형상 관리)에 이어, 어댑터·질의 범위·저장소 평면을 닫는다.

## 사용자 결정 (원문 요지)

1. **어댑터 — cg-colby (A) 확정**
   - "cg-colby (A) 확정 (Recommended)". 첫 구현 어댑터는 `colbymchenry/codegraph`로 간다.
   - 근거(이미 [[entity-codegraph]]에 정리됨): 단일 SQLite 파일(외부 DB 무), 30언어, 증분 인덱싱 1급,
     Node 런타임만 의존(가벼움), 레포별 물리 분리 자동(멀티 레포 정합성 안전), 1.2.0 안정 버전.
   - cgc(B)는 traversal 기능성 최상이나 의존 heavy·global 모드 격리 부담·Alpha(0.5.1)로 기각.

2. **질의 범위 — 단일 레포 우선**
   - "단일 레포 우선". v1은 한 레포 단위 질의만. cross-repo(A 레포 함수가 B 레포 호출·의존 추적)는 후순위.
   - cg-colby의 "레포별 독립 `.codegraph/`" 모델과 정합 → 저장소 모델이 단일 레포를 자연스럽게 지원.

3. **저장소 평면 — 별도 질의 서비스 평면**
   - "별도 질의 서비스 평면". 인덱스는 질의 전용 서비스(= 현재 MCP 서버)가 직접 소유·운영.
     관리 서버(Control Plane)와 상태를 분리한다.
   - 인덱스는 파생 데이터(언제든 재구축 가능)이므로 이력 DB([[decision-db-source-of-truth]]) 같은 SoT와
     성격이 다르고, 상시 온라인 서빙([[decision-code-index-mcp-serving]]) 요구를 품는다 → 전용 평면이 자연스럽다.

## 파생 (합의 직후 위키에 반영)

- 결정 3건 신규: [[decision-code-index-adapter-cg-colby]] · [[decision-code-index-single-repo-scope]]
  · [[decision-code-index-store-plane]]
- question 2건 answered: [[question-code-index-query-surface]](cross-repo=후순위, MCP tool 표면은 cg-colby
  단일 tool 철학을 따르되 어댑터가 환경변수 토글로 다중 노출), [[question-code-index-store]](별도 서비스 평면·버전 스냅샷)
- entity-codegraph: "후보 2종 조사" → "cg-colby(A) 확정, cgc(B) 기각"으로 상태 전환
