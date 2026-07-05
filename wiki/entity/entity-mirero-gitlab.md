---
type: entity
title: 사내 GitLab 환경 (미레로)
tags: [gitlab, infra, environment]
status: active
---

# 사내 GitLab 환경

사내 자체 호스팅 GitLab로, 문서 자동화의 소스 레포들이 여기 있다.
GitLab은 지원하는 두 SCM 커넥터 중 하나이며, GitHub과 함께 **동등한 1급 연동 대상**이다 → [[decision-scm-connector-abstraction]].

## 인프라

- 사내 자체 호스팅 GitLab + CI 러너
- **러너 → AI API 네트워크 경로 확보됨** ✅ (2026-07-05 확인, 폐쇄망 차단 아님) → [[question-runner-ai-network]]. 남은 것은 인증/실행 방식 → [[question-headless-claude-auth]]

## 대상 과제 (소스 4개 + 향후 확장)

X-LAB · ROC · Smart-ROS · SW-RCS — 개별 레포, C++/C#/JS/Python 혼재, Doxygen 주석 거의 없음.
경영진 방침: 문서 작성에 인적 리소스 투입 금지 (자동화의 근본 동기).

## 보안 원칙

group access token 최소 권한(소스 read + docs-hub write), 토큰·API 키는 CI masked variable로만,
서버 API는 사내망 한정 (인증 방식 → [[question-server-deploy-auth]]).

전체 그림: [[overview]]
