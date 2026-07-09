# 🏠 wiki_pipeline 지식 위키

> 사내 GitLab 다중 과제 AI 문서 자동화 시스템의 **설계 지식 베이스**.
> Andrej Karpathy의 [LLM Wiki](https://github.com/Astro-Han/karpathy-llm-wiki) 3계층 패턴을 따른다 — 원본을 불변 보존하고, LLM이 지식 페이지로 증류·유지하며, 스키마(헌법)가 그 규약을 정한다.

## 어디로 갈까

| 목적 | 진입점 |
|------|--------|
| **시스템 전체 그림**을 읽고 싶다 (서사·다이어그램·현재 진척) | → [[overview]] |
| **특정 지식**을 찾고 싶다 (결정·개념·질문·엔티티·요약) | → [[index]] (유형별 2계층 카탈로그) |
| **무슨 작업이 언제 있었나** 보고 싶다 (감사 추적) | → [[log-index]] (날짜별 연산 기록) |
| **규약·템플릿·검증기**를 확인하고 싶다 | → [[schema]] (`docs/schema/`) |

## 3계층 구조 (Karpathy LLM Wiki)

```
docs/
├─ raw/        📦 불변 원본 — 논의 기록·외부 자료. 수정 금지, 추가만.
├─ wiki/       📚 LLM이 유지하는 지식 계층 (이 위키가 곧 상태)
│  ├─ overview.md            시스템 서사 허브
│  ├─ index.md               유형별 지식 카탈로그 (lazy-loading 2계층)
│  ├─ concept/ decision/ entity/ question/ summary/   지식 페이지
│  └─ log/                   날짜별 연산 기록 + log-index (감사 추적)
└─ schema/     ⚖️ 헌법 — 구조·규약·워크플로우의 단일 기준
   ├─ schema.md              규약 본문 (SSOT)
   ├─ templates/             유형별 노트 스타터 6종
   └─ validate_frontmatter.py  frontmatter 자동 검증기
```

- **raw**는 진실의 앵커다 — 절대 수정하지 않는다.
- **wiki**는 LLM이 ingest / query / lint 워크플로우로만 갱신한다. log·index 모두 이 안에 산다("위키가 곧 상태").
- **schema**는 위키 밖의 헌법으로, 느리고 의도적으로만 바뀐다.

## 이 위키를 다루는 법 (워크플로우)

작업 전 **반드시 [[schema]]를 먼저 읽는다.** 단일 작업이 명확하면 아래 스킬을 직접, 모호하거나 여러 작업을 엮으면 `wiki-ops` 라우터를 쓴다.

- **ingest** — 새 지식을 raw/에 보존하고 wiki/로 증류 (`/ingest`)
- **query** — 위키를 근거로 질문에 답하고, 가치 있는 합성은 다시 파일링 (`/query`)
- **lint** — 무결성 점검·수정. 먼저 `python docs/schema/validate_frontmatter.py` (`/lint`)

모든 연산은 오늘 날짜 `wiki/log/<YYYY-MM-DD>.md`에 append 된다.
