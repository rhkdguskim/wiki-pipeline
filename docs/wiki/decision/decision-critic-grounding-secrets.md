---
type: decision
title: critic 확장 = 근거 대조 + 시크릿 기재 금지 (dev-guide·api-protocol 한정)
tags: [themes, critic, verification, security]
status: active
---

# critic 확장 = 근거 대조 + 시크릿 기재 금지

신규 테마 2종(dev-guide · api-protocol)은 정확도 요구가 특히 높다 — 환경 구성 단계가 틀리면
온보딩에 역효과, 실존하지 않는 엔드포인트가 기재되면 문서 신뢰가 무너진다. 이를 critic
([[entity-docu-automatic]]) 검증 기준 확장으로 막는다. 원본 논의: [[2026-07-06-theme-detail-grilling]]

## 결정 (두 테마 한정)

1. **근거 대조**: 문서의 모든 명령·설정·엔드포인트는 frontmatter `source_files` 안에 **실존 근거**가
   있어야 한다. 근거 없는 항목은 FAIL — 기존 재시도(최대 2회) 사이클을 그대로 재사용 (구조 변경 없음).
   근거 파일에는 코드뿐 아니라 **레포 내 문서**(README 등)도 포함된다 → [[decision-devguide-grounding-scope]]
2. **시크릿 기재 금지**: 토큰·패스워드·자격증명 **값**은 문서 기재 금지, 환경변수 **이름**으로만
   언급한다 (예: "CI 변수 `NUGET_TOKEN` 필요"). critic 검사 항목에 시크릿 패턴 검출을 추가
3. 사내 URL·피드 주소는 **허용** — docs-hub가 사내 전용이므로 문서 효용을 유지한다

## 근거

- MR 리뷰 게이트([[decision-mr-review-gate]])가 있어도 리뷰어가 모든 명령·엔드포인트를 재현
  검증하기는 어렵다 — 기계 검증이 먼저 거르는 편이 싸다
- 시크릿 값이 문서로 복제되면 원본을 회전(rotation)해도 문서에 잔존한다

## 기각 대안

- **기존 critic 그대로** (테마 적합성만) — 부정확 위험을 MR 리뷰에 전가
- **결정적 외부 검증** (api-protocol을 빌드 산출 OpenAPI 스펙과 자동 대조, dev-guide 명령 dry-run) —
  가장 강력하지만 파이프라인에 새 검증 단계가 필요해 구현 비용이 크다. **Phase 3+ 후보로 보류**
- **사내 정보 전면 마스킹** (URL까지) — 환경 구성 문서의 핵심 정보가 빠져 효용 급감

관련: 테마 정의는 [[decision-theme-scope-expansion]]
