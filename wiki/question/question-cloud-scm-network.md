---
type: question
title: 클라우드 SCM(github.com·gitlab.com) 아웃바운드 네트워크 경로가 열려 있는가
tags: [network, scm, github, gitlab-com, phase-1, blocking]
status: open
---

# 질문: 관리 서버 VM·러너에서 github.com/gitlab.com로 아웃바운드 HTTPS가 열려 있는가

[[decision-scm-multi-instance-github-mvp]]로 클라우드 SCM(github.com·gitlab.com) 레포를 MVP 소스로
받기로 했다. 이 커넥터가 실제로 동작하려면 **관리 서버 VM과 Data Plane 러너**에서 클라우드 SCM 호스트로의
**아웃바운드 HTTPS 경로**가 열려 있어야 한다.

## 왜 열려 있는가

- **AI API 경로는 확인됨** — 러너→AI API 아웃바운드는 이미 뚫려 있다 → [[question-runner-ai-network]] ✅.
- **클라우드 SCM 경로는 미확인** — 사내망에서 github.com/gitlab.com HTTPS가 방화벽·프록시로 막혀 있을 수 있다.
  AI API가 열렸다고 임의 외부 호스트가 열린 것은 아니다.

## 왜 blocking인가

[[2026-07-07-ops-backend-plan]]에서 이 확인은 **Phase 1(SCM 커넥터 계층) 실측 전에 선행**돼야 한다고 못박았다.
경로가 막혀 있으면 GitHubConnector·gitlab.com GitLabConnector의 compare/submit이 아예 실행되지 않으므로
Phase 1 완료 기준(github.com·gitlab.com 레포를 소스로 diff→문서 생성)을 검증할 수 없다 → **진행 차단(blocking)**.

## 답이 나오면

경로 개방 여부(및 프록시 경유 필요 여부)가 확정되면 decision으로 승격하고 이 질문을 `answered` + `blocking` 태그 제거.

관련: [[decision-scm-multi-instance-github-mvp]] · [[question-cloud-scm-token-policy]] · [[question-runner-ai-network]] · [[entity-mirero-gitlab]]
소스: [[2026-07-07-ops-backend-plan]]
