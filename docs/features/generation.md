# 문서 생성 — 생성 엔진(Docu-Automatic) 통합 (FR-7)

← [문서 인덱스](../README.md)

> 엔진 레포: https://github.com/jaeCheon8587/Docu-Automatic (산출물 6개 완료 상태)

## 요구사항

| ID | P | 요구사항 |
|----|---|----------|
| FR-7 | P0 | **AI 문서 생성**: 생성 엔진(task-pipeline)을 headless로 호출. 문서(테마)당 1회/run. 엔진 정책 준수: 재시도 최대 2회, 2회 초과 시 `auto_generated_warning` 태그 후 저장, 3연속 FAIL 시 중단 |

## 엔진 구조 (v4, 1단계 오케스트레이션)

```
Main CLI (Level 0): skills/task-pipeline/SKILL.md 실행 — 테마 루프 + 재시도 + 저장
  ├── scout (Level 1):       코드 탐색 + 문서화 필요 판단 + 요구사항서 작성
  ├── docu-writer (Level 1): 요구사항서 기반 .md 작성
  └── critic (Level 1):      frontmatter 유효성 + 테마 적합성 독립 검증
```

- 테마 **순차 순회**, 테마별 4단계 사이클(판단 → 작성 → 검증 → 저장)
- **Full Reset**: 매 테마마다 에이전트 신규 생성 (컨텍스트 오염 방지, 비용 1.0x)
- **execution-log.md**: 파일 기반 상태 추적 → run 아티팩트로 보존 ([monitoring FR-15](./monitoring.md))
- 1차 스코프 4개 테마: `getting-started/intro` · `getting-started/requirements` · `architecture/overview` · `architecture/component-diagram`
- frontmatter 스키마 (필수 9 + 선택 2): `source_files`, `last_commit`, `theme` 등 → [change-detection](./change-detection.md)의 매핑 기반
- 콜드 스타트: Day 0 뼈대 → 점진 채움 → [sources FR-3](./sources.md)
- 비용 최적화: 판단 단계 Haiku, 코드 요약 캐싱, 불필요 테마 스킵

## 기존 v4 설계와의 조정 사항

| 항목 | 기존 (v4) | 본 시스템 | 비고 |
|------|-----------|----------|------|
| 트리거 | git push 시 각 제품 레포 CI에서 AI 실행 | 야간 pull 배치 | 엔진은 호출 시점만 바뀌고 그대로 재사용 → [scheduling](./scheduling.md) |
| 산출물 저장 | 각 레포 `docs-auto` 브랜치 → 중앙 배치가 pull하여 빌드 | docs-hub에 직접 브랜치 + **MR** | MR 권장: 사람 리뷰 게이트([G5](../goals.md)). **최종 확정 필요** → [open-questions](../open-questions.md) #5 |
| 변경 감지 입력 | 직전 커밋 git diff | 누적 구간 diff (`last_processed_sha`~HEAD) | scout 입력 계약에 누적 diff 전달하도록 확장 |
| 중앙 배치 빌드 | 스케줄 기반 일괄 빌드 | 유지 — MR 머지로 docs-hub main 변경 시 Docusaurus 빌드/배포 | |
| 실행 환경 | Claude Code CLI (대화형 전제) | CI 러너 headless (`claude -p`) | **Phase 1 최우선 검증 항목** → [roadmap](../roadmap.md) |
