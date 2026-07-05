---
type: entity
title: 사내 GitLab 환경 (미레로)
tags: [gitlab, infra, environment]
status: active
---

# 사내 GitLab 환경

## 인프라

- 사내 자체 호스팅 GitLab + CI 러너
- 기존 문서 사이트: http://110.110.10.70:8080/ (Docusaurus) → [[question-existing-site-relation]]
- **러너 → AI API 네트워크 경로 미확인** ⛔ → [[question-runner-ai-network]]

## 대상 과제 (소스 4개 + 향후 확장)

X-LAB · ROC · Smart-ROS · SW-RCS — 개별 레포, C++/C#/JS/Python 혼재, Doxygen 주석 거의 없음.
경영진 방침: 문서 작성에 인적 리소스 투입 금지 (자동화의 근본 동기).

## 스택 제안 (미확정 → [[question-server-stack-db]])

관리 서버 ASP.NET Core Minimal API + BackgroundService + SignalR / DB SQLite→Postgres / 파이프라인 Python.

## 보안 원칙

group access token 최소 권한(소스 read + docs-hub write), 토큰·API 키는 CI masked variable로만,
서버 API는 사내망 한정 (인증 방식 → [[question-server-deploy-auth]]).

전체 그림: [[overview]]
