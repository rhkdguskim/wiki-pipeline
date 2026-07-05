---
type: decision
title: 소스 빌드 대신 릴리스 아티팩트 소비
tags: [artifact, build, release]
status: active
---

# 결정: 파이프라인은 빌드하지 않고 아티팩트를 소비한다

[[entity-manual-pipeline]]은 앱을 소스에서 빌드하지 않는다. 빌드는 기존 CI가 담당하고 릴리스가
아티팩트를 생성하므로, 파이프라인은 **그 버전의 아티팩트를 가져와** MCP 파일전송으로 배포한다
→ [[entity-remote-control-mcp]].

## 근거

- **빌드 책임 중복 제거** — 빌드 파이프라인은 이미 존재·검증됨. 다시 빌드하면 도구체인·환경을 이중 유지해야 함.
- **릴리스가 곧 소재** — 릴리스 아티팩트는 "문서화 대상 버전"의 정확한 산출물이다. 트리거와 짝 → [[decision-release-tag-trigger]].

## 기각 대안

- **파이프라인 내 재빌드** — 아티팩트 획득 실패에 독립적이라는 장점은 있으나, 빌드 환경·의존성·서명까지 복제해야 해 비용이 크고 "릴리스된 그 바이너리"와 어긋날 위험.

관련: [[entity-manual-pipeline]] · 원본: [[2026-07-05-manual-extraction-pipeline]]
