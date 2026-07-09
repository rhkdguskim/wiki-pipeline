---
type: decision
title: 브랜치 선택(개발/배포) + 좀비 소스 비활성화 (protected 분기 재활성화)
tags: [registration, branch, compare-api, disable, lifecycle]
status: active
---

# 결정: 등록의 개발/배포 브랜치 선택 + compare 404 시 자동 비활성화, 재활성화는 protected 여부로 분기

한 레포 등록은 **개발 브랜치 1 + 배포 브랜치 1(고정 2)** 을 지정한다
([[decision-repo-dev-release-registration]]). 등록된 소스의 야간 compare가 404를 반환하면
(브랜치·레포 소실 = "좀비 등록") **자동 비활성화 + 알림**하고, **재활성화는 브랜치의 `protected`
여부로 분기**한다.

## 브랜치 선택 = 개발 1 + 배포 1 (역할 고정)

- 등록 UI는 `GET /projects/:id/repository/branches` 목록에서 **개발 브랜치·배포 브랜치를 각각 하나씩** 고른다.
- 배포 브랜치 기본값은 `default_branch`로 제안한다(master/main 혼재라 하드코딩 금지 → [[entity-mirero-gitlab]]).
- 두 브랜치는 역할이 다른 문서를 낳고(개발=최신 기술문서·compare 야간, 배포=릴리스 문서·태그 트리거),
  docs-hub에서 `<레포폴더>/dev/`·`/release/`로 갈린다 → [[decision-docs-hub-folder-rule]].
- 좀비 처리(아래)는 등록 안의 **두 브랜치 각각**에 적용된다.
- 폐기된 옛 정책: "모든 브랜치 노출 + 아무 브랜치나 다중 등록(정책 C)" — 레포×브랜치 원자단위와 함께
  대체됨 → [[decision-repo-registration-flow]](superseded) · [[decision-repo-dev-release-registration]].

## 좀비 등록 처리 = B (자동 비활성화 + 알림, 삭제 아님)

- 야간 compare가 **404**(브랜치·레포 소실)를 반환하면 `sources.enabled = false`로 **자동 비활성화**
  하고 **대시보드 알림**한다. **등록을 삭제하지 않는다.**
- 근거: run_items 이력·등록 메타를 보존해야 감사 추적이 끊기지 않는다 —
  [[decision-db-source-of-truth]]가 이미 "run_items 삭제 안 함, 비활성화 후에도 이력 보존"을 규정.
- **5xx·타임아웃은 브랜치 소실이 아니므로 재시도**(비활성화 아님) — 404만 소실 신호.
- 기각: A(즉시 삭제) — 이력 소실. C(무시하고 계속 재시도) — 좀비가 배치를 계속 오염.

## 브랜치 소실 후 재활성화 — `protected` 플래그로 분기

| 브랜치 유형 | 첫 404 | 브랜치 복귀 시 |
|------------|:------:|--------------|
| **protected / default** | 즉시 비활성화 | **자동 재활성화** — 안정 브랜치라 진동(flapping) 없음 |
| **비-protected** (feature류) | 즉시 비활성화 | **수동 재활성화만** — 자동 복귀를 빼서 flapping·감사 단절 차단 |

- GitLab이 API로 알려주는 `protected` 플래그로 시스템이 안정/불안정을 실제 구분한다 —
  정책 C(아무 브랜치 허용)의 유연성과 "안정 브랜치 가정"이 이 분기로 정합한다.
- 모든 비활성화·재활성화는 대시보드에 알린다.

## 파생 효과

- **pull 모델의 실패 경로를 채움** — 밤 compare가 404를 만나는 런타임 경로가 이제 정의된다
  → [[decision-pull-model]].
- **방치 소스 판정과 인접** — CI-less·방치 소스의 활성/방치 자동 판정 논의와 맞닿는다
  → [[question-ci-less-source-policy]].

근거: [[2026-07-06-registration-grilling]] · 실측: [[2026-07-06-wish-gitlab-api-survey]].
관련: [[decision-repo-registration-flow]] · [[decision-docs-hub-folder-rule]] · [[decision-db-source-of-truth]] · [[decision-pull-model]] · [[overview]]
