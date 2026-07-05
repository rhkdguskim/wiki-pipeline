---
type: question
title: 인덱스 저장소 소유·경계·재인덱싱 중 가용성
tags: [code-index, storage, availability, phase-2]
status: answered
---

# ❓ 코드 인덱스는 어디에 속하고, 쓰는 동안 읽기는 어떻게 보장하나

인덱스는 **파생 데이터**(언제든 재구축 가능)라 이력 DB([[decision-db-source-of-truth]])와 성격이 다르다.
[[decision-code-index-pipeline]]의 읽기 경로가 온라인이므로 저장소에 새 요구사항이 생긴다.

- **소유·경계** — 인덱스 저장소는 어느 평면에 속하나? Data Plane 산출물인가, 질의 서비스의 상태인가
- **가용성** — 짧은 주기 재인덱싱 **중에도** 직전 버전으로 질의 가능해야 한다 (쓰기가 읽기를 막으면 안 됨)
- **일관성** — 갱신 교체 단위(레포 단위 원자 교체?)와 질의 중 버전 혼재 방지
- 기술 스택(저장 엔진) 제안은 요구사항 확정 전까지 보류

## 답

- **소유 평면** = **별도 질의 서비스 평면**(현재 MCP 서버). Control Plane과 상태 분리 → [[decision-code-index-store-plane]]
- **가용성·일관성** = sha 결부 버전 스냅샷 + 원자 교체. 재인덱싱 중 직전 버전 서빙 → [[decision-code-index-versioning]]
- **저장 엔진** = 어댑터 정책 따름. cg-colby([[decision-code-index-adapter-cg-colby]]) 채택 시 SQLite 파일이 이 평면 산출물.

소스: [[2026-07-05-code-index-pipeline]] · [[2026-07-05-code-index-finalization]]
