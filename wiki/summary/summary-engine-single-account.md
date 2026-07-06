---
type: summary
title: 엔진 단일 계정 인증 논의 요약 (2026-07-06)
tags: [engine, auth, mvp]
status: active
---

# 엔진 단일 계정 인증 논의 요약

> 원본: [[2026-07-06-engine-single-account]]

Claude Code를 로그인 방식으로 구동하는 엔진 인증을 어떻게 둘지 논의한 기록.

## 요지

- 처음엔 여러 계정을 라운드 로빈으로 회전(로그아웃/로그인 + 만료 fallback)하는 안을 검토했으나, MVP는 **단일 계정**으로 시작하기로 정리.
- 단일 계정이므로 대시보드 등록 UI/백엔드에 **로그인 아이디/패스워드 설정**이 필요하다는 요구를 확인.

## 파생 페이지

- 결정: [[decision-engine-single-account-auth]]
- 갱신: [[question-headless-claude-auth]] · [[question-mvp-scope]] · [[question-secret-storage-security]]

전체 그림 → [[overview]]
