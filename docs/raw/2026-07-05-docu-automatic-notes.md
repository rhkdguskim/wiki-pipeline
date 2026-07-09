# Docu-Automatic 레포 분석 노트 (2026-07-05)

> raw source — 불변. https://github.com/jaeCheon8587/Docu-Automatic 를 클론하여
> README.md, docs-automation/PRD.md, docs/01.설계-결정사항.md, docs/02.아키텍처.md 를 분석한 기록.

## 레포 정체

Docusaurus 문서 자동화 파이프라인의 **문서 생성 엔진**. Claude Code CLI 기반.
"git push 시 AI가 코드를 분석하여 기술 문서(.md)를 자동 생성하고, Docusaurus 사이트로 빌드/배포하는 파이프라인."

## 배경 (원문 발췌)

- 팀 내 여러 제품군이 개별 Git 레포로 관리됨 (C++, C#, JavaScript, Python)
- 경영진 방침: 문서 작성에 인적 리소스를 투입하지 말 것
- 기존 코드베이스에 Doxygen 주석이 거의 없어 AI가 코드를 직접 분석하여 문서 생성

## 아키텍처 v4 (1단계 오케스트레이션)

v3의 3단계 중첩(Main → task-orchestrator → writer/critic)이 Claude Code의 "서브 에이전트가
서브 에이전트를 생성할 수 없음" 제약으로 실행 불가 → v4에서 1단계로 평탄화.

```
Main CLI (Level 0): 테마 루프 + 판단 + 오케스트레이션 + 재시도 + 저장
  ├── scout (Level 1):       탐색 + 판단 + 요구사항서 (리프)
  ├── docu-writer (Level 1): md 작성 (리프)
  └── critic (Level 1):      독립 검증 (리프)
```

### 테마별 4단계 사이클

| 단계 | 수행자 | 내용 |
|------|--------|------|
| 판단 | Agent(scout) | git diff + 테마 정의 분석 → 문서화 필요 여부 판단 → 요구사항서 작성 |
| 작성 | Agent(docu-writer) | 요구사항서 + 관련 코드 → YAML frontmatter 포함 .md 생성 |
| 검증 | Agent(critic) | frontmatter 유효성 + 테마 적합성 2단계 검증 |
| 저장 | Main | .md 저장 + execution-log 기록. Fail 시 최대 2회 재시도 |

### 핵심 전략 (원문)

- **Full Reset**: 매 테마마다 에이전트 신규 생성 (컨텍스트 오염 방지, 비용 1.0x vs Resume 1.8~3.6x)
- **순차 순회**: 테마 간 병렬 처리 금지. 품질과 안전성 우선
- **3연속 FAIL 시 파이프라인 중단**, 재시도 2회 초과 시 `auto_generated_warning` 태그 후 저장
- **execution-log.md**: YAML 상태 헤더 + 결과 테이블. 오토 컴팩트 시 변수 소실 대비 파일 기반 상태 추적

## 1차 스코프: 페이지 단위 테마 4개

| 테마 ID | 관점 | 대상 독자 |
|---------|------|----------|
| `getting-started/intro` | 프로젝트 전체 소개 | 모든 방문자 |
| `getting-started/requirements` | 설치/실행 환경과 조건 | 설치자, 운영자 |
| `architecture/overview` | 시스템 전체 구조와 모듈 관계 | 신규 팀원, 개발자 |
| `architecture/component-diagram` | S/W별 컴포넌트 구성 | 개발자 |

- 테마 단위가 "제품별 7테마"에서 "페이지 단위(1테마=1md)"로 변경됨 — 실제 사이트 구조와 1:1 매핑
- 2차 확장 예정: 제품별 서브페이지 28페이지, 라이브러리, 개발 가이드 등

## frontmatter 스키마 (필수 9 + 선택 2)

title, sidebar_label, sidebar_position, section, theme, auto_generated, **source_files**(원본 소스 파일 목록),
**last_commit**(마지막 분석 커밋), generated_at + 선택: auto_generated_warning, tags

## 원 설계의 전체 흐름 (v4 기준, wiki-pipeline 이전)

```
main push → CI 트리거 → [코드 분석 + AI .md 생성] → docs-auto 브랜치에 push
                → 중앙 처리(스케줄 배치): 각 레포 docs-auto pull → frontmatter 기반 분류
                → sidebars.js 갱신 → Docusaurus 빌드 → 배포
```

## 미결 사항 (원 레포 기준, 발췌)

CI/CD 구체 설정(#3), 스케줄 주기(#4), docs-auto 브랜치 관리(#5), 비용 예측(#6),
문서 품질 기준(#7), 인간 리뷰 프로세스(#8), sidebars.js 자동 생성(#9), 기존 수동 문서 병합(#10)

## 콜드 스타트 전략

Day 0: 코드 내용 분석 없이 디렉터리 트리 + 파일명으로 뼈대 생성 → Day 1~N: push마다 점진 채움
→ Day 30+: 자연 충실화, 드물게 변경되는 파일은 수동 전체 스캔 옵션

## 산출물 현황 (완료)

스킬 4개(task-pipeline, docu-writer-skill, critic-skill, theme-definitions) + 에이전트 2개(docu-writer, critic)
— scout 포함 시 에이전트 3개 체계. 실행 환경: Claude Code CLI (대화형 전제).
