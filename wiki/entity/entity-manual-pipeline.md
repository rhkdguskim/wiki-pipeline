---
type: entity
title: 매뉴얼 추출 파이프라인 (신규)
tags: [manual, pipeline, mcp, data-plane]
status: active
---

# 매뉴얼 추출 파이프라인

실행 중인 Windows 앱을 MCP로 구동·관측해 사용자/엔지니어 매뉴얼을 생성하는 신규 파이프라인.
[[entity-docu-automatic]](코드→기술문서)과 **별개 기능**이며, 관리 서버·[[entity-docs-hub]]·MR 게이트만
공유한다 → [[decision-manual-pipeline-separate]].

## 실행 흐름 (7단계)

1. **아티팩트 수집** — 릴리스 태그 → 그 버전 아티팩트 획득(외부 빌드 CI 산출물 소비) → [[decision-artifact-consumption]], [[decision-release-tag-trigger]]
2. **배포** — MCP 파일전송으로 앱 실행 환경에 전송·배치 → [[entity-remote-control-mcp]]
3. **실행** — 그 환경에서 앱 기동 (인증·데이터 등 전제 충족)
4. **전수 순회** — MCP UI 자동화로 모든 기능 순회(하이브리드) → [[decision-hybrid-app-traversal]]. 화면·컨트롤·전이·캡처를 관측 로그로 수집 → [[concept-observation-grounding]]
5. **매뉴얼 생성 + diff** — 관측 + 커밋 히스토리 → add/update/delete → [[decision-commit-history-manual-diff]], [[concept-manual-lifecycle-diff]]
6. **제출** — docs-hub 브랜치 + MR → [[decision-mr-review-gate]]
7. **보고** — MR 성공 후에만 버전 포인터 전진 → [[concept-idempotent-sha]]

## Data Plane 위치

Docu-Automatic과 함께 **Data Plane의 두 번째 파이프라인**으로, 사내 **Windows CI** 위에서 돈다
(기존 파이프라인도 Windows CI 구동 → Windows 앱 실행·UI 자동화 기반이 이미 존재) → [[decision-control-data-plane-split]].

## app 등록

관리 서버 등록 종류가 둘로: 기존 `source`(compare용)와 신규 `app`.
`app`은 **소스 레포**(커밋 히스토리) + **아티팩트 출처**(릴리스) + **실행 호스트 IP/port**(세션 MCP 제어) + **시크릿**(로그인 등, UI 테스트용) + 시나리오 세트 + `last_documented_version`을 갖는다 → [[decision-app-host-connection]].

원본: [[2026-07-05-manual-extraction-pipeline]] · 요약: [[summary-manual-extraction-pipeline]] · 전체 그림: [[overview]]
