# 변경 감지 · 영향 분석 (FR-5~6)

← [문서 인덱스](../README.md)

"지난밤 이후 무엇이 바뀌었고, 어느 문서를 다시 생성해야 하는가"를 결정한다. AI 호출이 커밋 수가 아닌
**영향 문서 수**에 비례하게 만드는 핵심 단계 ([G2](../goals.md)).

## 요구사항

| ID | P | 요구사항 |
|----|---|----------|
| FR-5 | P0 | **변경 감지**: 소스별 compare API(`from=last_processed_sha, to=HEAD`)로 변경 파일 집합 조회. sha가 현재 브랜치에서 유효하지 않으면(force-push 등) "최근 N일" fallback으로 전환하고 경고 기록 |
| FR-6 | P0 | **영향 분석**: 변경 경로를 문서 frontmatter(`source_files`, `theme`)와 대조해 재생성 대상 테마 산출. 어떤 문서에도 매핑되지 않는 변경은 **신규 문서 후보로 리포트** (침묵 누락 금지) |

## compare API가 핵심인 이유

`last_processed_sha`~HEAD 구간을 한 번에 잘라 **최종 변경 파일 집합**만 받는다.
커밋이 20개 쌓였든 100개든, 같은 문서에 영향 주는 변경은 자연스럽게 하나로 병합된다 —
큐·디바운스 로직을 코드로 짤 필요가 없다.

## 경로 ↔ 문서 매핑

생성 엔진의 frontmatter 스키마가 매핑의 기반이다 (`source_files`: 원본 소스 파일 목록, `theme`: 테마 ID)
→ [generation](./generation.md). glob 패턴 지원 여부는 [open-questions](../open-questions.md) 참고.

## 방어 로직

- **sha 유효성 검증**: `last_processed_sha`가 현재 브랜치의 조상인지 확인. 아니면(force-push/rebase)
  "최근 N일" fallback + 경고. 예방책으로 소스 레포 main protect 권장 → [nfr 실패 시나리오](../nfr.md)
- **미매핑 변경**: 버리지 않고 run 결과에 "신규 문서 후보" 목록으로 노출 → [monitoring](./monitoring.md)
