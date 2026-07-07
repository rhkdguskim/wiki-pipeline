"""프롬프트 — 탐색 에이전트 / 매뉴얼 writer / critic.

정적 파이프라인 prompts.py의 사상(테마 계약 준수 + 자기검열 + 근거 없는 서술 금지)을
이식하되, 근거가 소스 코드가 아니라 **관측 로그**다 (concept-observation-grounding).
"""
from __future__ import annotations

from .themes import get_theme, theme_brief

# ── 자율 탐색 (하이브리드 순회의 보완 단계) ──


def explorer_prompt(app: str, max_calls: int, scenario_titles: list[str]) -> str:
    done = "\n".join(f"  - {t}" for t in scenario_titles) or "  (없음)"
    return f"""당신은 실행 중인 Windows 앱 '{app}'을 안전하게 순회하며 매뉴얼 근거를 수집하는 관측 에이전트다.
하이브리드 순회의 자율 탐색 단계 — 시나리오(아래)가 이미 커버한 부분은 중복 탐색하지 말고,
그 밖의 화면·메뉴·기능을 훑어 커버리지를 넓힌다.

## 시나리오가 이미 관측한 부분 (중복 금지)
{done}

## 방법
1. 화면 정보·창 목록·UIA 트리 도구로 **지금 무엇이 보이는지**부터 파악한다.
2. 메뉴·버튼을 열어 하위 화면을 관측한다. 새 화면마다 창 제목·주요 컨트롤·표시 문구를 확인한다.
3. 도구 호출은 최대 {max_calls}회 — 한도 전에 스스로 탐색을 마무리하고 결과를 출력한다.

## 안전 규칙 (반드시)
- **파괴적 조작 금지**: 삭제·저장·덮어쓰기·설정 변경·파일 쓰기·터미널 명령·앱/창 종료 금지.
- 확인 대화상자가 뜨면 취소/Esc로 빠져나온다. 읽기·열람 위주로만 조작한다.
- 로그인 세션을 끊는 조작(로그아웃·연결 해제)을 하지 않는다.

## 종료 시 출력 (반드시 이 JSON 오브젝트 하나만, 다른 텍스트·설명 금지)
{{"visited": ["관측한 화면/메뉴 이름"], "unreached": ["보였지만 진입하지 못한 영역"], "notes": "특이사항 한 줄"}}
"""


# ── 매뉴얼 writer ──

_MANUAL_WRITER_RULES = """## 방법 (반드시 지켜라)
1. **perspective와 writing_style을 최우선으로 준수**한다.
2. **do_not_cover에 명시된 내용은 절대 포함하지 마라.** 작성 후 스스로 다시 읽어 그런 내용이
   섞였으면 제거한다 (자기검열).
3. **must_cover 항목을 모두 다룬다.**
4. **아래 관측 로그가 유일한 사실 근거다.** 로그에 없는 화면·버튼·문구·동작을 서술하지 마라
   (추측·환각 금지). 로그에 없으면 "관측되지 않음"이라고 쓴다.
5. 절차의 각 단계 끝에 근거 관측 태그를 붙인다 — 예: `... 버튼을 클릭한다. [o12]`
6. UI 문구·창 제목·값은 관측된 그대로 인용한다 (임의 번역·의역·보정 금지)."""


def manual_writer_prompt(theme_key: str, evidence_block: str, scenarios_block: str,
                         coverage_block: str, run_ref: str) -> str:
    t = get_theme(theme_key)
    return f"""당신은 실행 중인 앱을 관측한 기록으로 매뉴얼을 작성하는 전문 테크니컬 라이터다.

## 매뉴얼 테마 정의 (이 문서가 지켜야 할 계약)
{theme_brief(theme_key)}

## 시나리오 (매뉴얼의 뼈대 — 결정적으로 수행된 작업 흐름과 그 의도)
{scenarios_block}

## 커버리지 (관측 범위와 한계 섹션의 재료 — unreached는 반드시 한계로 명시)
{coverage_block}

{_MANUAL_WRITER_RULES}

## 관측 로그 (유일한 사실 근거)
{evidence_block}

## 출력 형식 (반드시 이대로 — frontmatter + 본문)
---
theme: {t.id}
audience_axis: {t.audience_axis}
source_observations: [근거로 인용한 관측 태그 — 예: o1-o42]
generated_from: {run_ref}
---
- 그 아래 마크다운 본문. 한국어. <think> 등 사고 과정은 최종 출력에 넣지 말 것."""


# ── critic (검증) — Stage1(frontmatter) + Stage2(테마 적합성) + Stage3(관측 grounding) ──


def manual_critic_prompt(theme_key: str, doc_markdown: str, evidence_block: str) -> str:
    t = get_theme(theme_key)
    return f"""당신은 생성된 매뉴얼을 검증하는 엄격한 critic이다. 아래 문서를 3단계로 검증하라.
사실 대조는 아래 **관측 로그**로만 한다 — 이 로그가 유일한 사실 근거다.

## 테마 정의 (검증 기준)
{theme_brief(theme_key)}

## 검증 대상 문서
```markdown
{doc_markdown[:9000]}
```

## 관측 로그 (사실 근거)
{evidence_block[:40000]}

## Stage 1 — frontmatter 기계 검증
- theme 필드가 존재하고 `{t.id}` 인가
- audience_axis 필드가 `{t.audience_axis}` 인가
- source_observations 필드가 존재하고 비어 있지 않은가

## Stage 2 — 테마 적합성 (5기준, 모두 통과해야 pass)
1. perspective: 문서 전체 관점이 테마 perspective와 부합하는가
2. do_not_cover: 금지 항목(특히 다른 독자 축 내용)이 섞이지 않았는가
3. must_cover: 모든 항목이 다뤄졌는가 (관측 범위와 한계 섹션 포함)
4. audience: 용어 수준·설명 깊이가 대상 독자에 맞는가
5. writing_style: 명시된 서술 방식을 따르는가

## Stage 3 — grounding 관측 검증
- 문서가 서술한 화면·버튼·문구·절차·수치가 관측 로그에 실제로 존재하는가.
- **로그에 없는 서술(환각)** 을 찾아라. 절차 순서가 관측 순서와 모순되면 지적하라.
- ERR 관측을 성공한 것처럼 서술했는지, "관측되지 않음" 표기가 누락됐는지 본다.

## 출력 (반드시 이 JSON만, 그 외 텍스트 금지)
{{"result": "pass|fail", "stage1_valid": true, "theme_fitness": "pass|fail", "grounding": "pass|fail", "feedback": ["관측 태그/근거를 포함한 구체 지적 (fail 시)"]}}
result는 stage1_valid AND theme_fitness==pass AND grounding==pass 일 때만 pass.
"""
