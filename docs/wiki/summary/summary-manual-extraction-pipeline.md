---
type: summary
title: 매뉴얼 추출 파이프라인 설계 논의 요약
tags: [manual, mcp, pipeline]
status: active
---

# 요약: 사용자/엔지니어 매뉴얼 추출 파이프라인

원본: [[2026-07-05-manual-extraction-pipeline]]

Windows 앱을 실제로 구동해 관측한 화면·흐름을 근거로 사용자/엔지니어 매뉴얼을 생성하는 **신규 파이프라인**.
코드 diff를 읽는 [[entity-docu-automatic]]과 별개이며, 관리 서버·docs-hub·MR 게이트만 공유한다
→ [[decision-manual-pipeline-separate]].

## 핵심 골격

릴리스 태그 → 아티팩트 획득 → MCP 파일전송으로 앱 실행 환경 배포 → MCP UI 자동화로 전수 순회 →
관측 + 커밋 히스토리로 매뉴얼 add/update/delete → docs-hub MR.

- 트리거는 릴리스/버전 태그 → [[decision-release-tag-trigger]]
- 소스 빌드 대신 아티팩트 소비 → [[decision-artifact-consumption]]
- 하이브리드 순회(시나리오 + 자율 탐색) → [[decision-hybrid-app-traversal]]
- 커밋 히스토리 + 관측으로 라이프사이클 판정 → [[decision-commit-history-manual-diff]], [[concept-manual-lifecycle-diff]]
- 근거는 실행 앱 관측 → [[concept-observation-grounding]]
- 앱=별도 호스트, IP/port 세션 MCP 제어 + 시크릿 등록 저장 → [[decision-app-host-connection]]
- 실행 주체 MCP → [[entity-remote-control-mcp]] · 파이프라인 → [[entity-manual-pipeline]]

## 파생 미결

[[question-app-exec-environment]] · [[question-ui-coverage-completeness]] · [[question-manual-delete-safety]] ·
[[question-scenario-set-ownership]] · [[question-manual-theme-taxonomy]] · [[question-mcp-auth-network]]
