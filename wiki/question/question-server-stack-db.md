---
type: question
title: 관리 서버 스택·DB 확정?
tags: [phase-2, stack]
status: open
---

# ❓ 관리 서버 스택·DB는 무엇으로 확정하는가?

제안: ASP.NET Core Minimal API + BackgroundService(cron) + SignalR / DB는 SQLite 시작 → Postgres.
팀 익숙 스택이라는 근거([[entity-mirero-gitlab]])는 있으나 최종 확정 전.

- 블로킹 대상: Phase 2 (관리 서버 개발)
- 관련: [[decision-db-source-of-truth]] (DB가 SoT라는 결정은 확정, 어떤 DB인지가 미결)
