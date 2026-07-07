"""프롬프트 — 원본 Docu-Automatic의 scout/docu-writer/critic 지시를 이식·강화.

원본 핵심 규칙을 반영:
- writer: perspective/writing_style 최우선, do_not_cover 자기검열, Read로 확인 안 한 것 서술 금지.
- critic: Stage1(frontmatter 기계 검증) + Stage2(테마 적합성 5기준 AND).
개선(원본에 없음): critic에 grounding(문서 주장 ↔ source_files 대조) 추가.
테마 정의는 themes.py 레지스트리에서 온다 (데이터 주도).
"""
from __future__ import annotations

from ..common_pipeline.verify import DOC_END_MARKER
from .themes import theme_brief

# ── init 계획 단계 (에이전트가 문서화 단위 결정) ──

def plan_system_prompt(ref: str, top_level: list[str]) -> str:
    tops = "\n".join(f"  - {t}" for t in top_level)
    return f"""당신은 사내 코드 저장소를 처음 문서화하기 위해 **문서화 계획**을 세우는 아키텍트다.

## 목표
이 저장소(버전 {ref[:10]})의 구조를 파악해, 최초 문서화(init)를 **어떤 단위로 나눌지** 결정한다.
저장소마다 구조가 다르다 — C++(CMake/솔루션), C#(.sln/.csproj), 혼합 등. 정해진 디렉터리
깊이로 기계적으로 나누지 말고, **이 저장소에 맞는 자연스러운 컴포넌트/빌드 단위**로 나눈다.

## 저장소 최상위 항목
{tops}

## 방법
1. list_dir / read_file 도구로 구조를 **최대 8회까지** 탐색한다 — 빌드 파일(.sln, .csproj,
   CMakeLists.txt, .vcxproj 등), 최상위 디렉터리, README/문서를 보고 컴포넌트 경계를 파악한다.
2. 서드파티/외부 라이브러리(3rdparty, vendor, external 등)와 빌드 산출물은 **문서화 단위에서 제외**한다.
3. 파악이 끝나면 도구를 멈추고, 문서화 단위 목록을 **JSON으로만** 출력한다.

## 출력 (반드시 이 JSON 형식, 그 외 텍스트/서술 금지)
{{"units": [{{"name": "짧은 단위명", "root_path": "대표 경로", "kind": "component|service|library|app", "why": "묶은 이유 한 줄"}}]}}
단위는 5~15개가 적당하다. 너무 잘게 쪼개지도, 저장소 전체를 한 덩어리로 두지도 마라.
"""


# ── docu-writer (문서 작성) ──

_WRITER_RULES = """## 방법 (원본 docu-writer 규칙 — 엄격히 지켜라)
1. **perspective와 writing_style을 최우선으로 준수**한다.
2. **do_not_cover에 명시된 내용은 절대 포함하지 마라.** 작성 후 스스로 다시 읽어 그런 내용이
   섞였으면 제거한다 (자기검열).
3. **must_cover 항목을 모두 다룬다.**
4. read_file / list_dir 도구로 소스를 **직접 읽어** 근거를 모은다 — 최대 6회. **Read로 확인하지
   않은 함수 동작·클래스 구조·수치를 서술하지 마라 (추측·환각 금지).** 모르면 "코드에서 확인되지 않음".
5. 같은 파일을 두 번 읽지 마라. 잘려도 재요청 말고 앞부분으로 판단하라. 6회 도달 시 즉시 문서 완성.
6. **문서를 완성해 내보내는 것이 우선**이다 — 무한 탐색 금지."""

_WRITER_OUTPUT = """## 출력 형식 (반드시 이대로 — frontmatter + 본문)
---
theme: {theme_id}
source_files: [실제로 Read/인용한 파일 경로들 — 최소 1개]
{origin_line}
---
- 그 아래 마크다운 본문. 한국어. <think> 등 사고 과정은 최종 출력에 넣지 말 것.
- 문서 맨 마지막 줄에 정확히 `{end_marker}` 를 붙인다 — 문서가 끝까지 완결됐다는
  표시다. 이 마커 없이 끝나면 잘린 문서로 판정돼 재작성된다."""


def _writer_prompt(*, theme_id: str, scope_block: str, origin_line: str) -> str:
    return f"""당신은 사내 코드 저장소의 기술문서를 작성하는 전문 기술 작가다.

## 테마 정의 (이 문서가 지켜야 할 계약)
{theme_brief(theme_id)}

## 이번 작업 대상
{scope_block}

{_WRITER_RULES}

{_WRITER_OUTPUT.format(theme_id=theme_id, origin_line=origin_line, end_marker=DOC_END_MARKER)}
"""


def diff_writer_prompt(theme_id: str, changed_files: list[str], from_sha: str, to_sha: str) -> str:
    files = "\n".join(f"  - {f}" for f in changed_files[:40])
    scope = (f"- 모드: **증분(diff)** — 변경 구간 {from_sha[:10]} -> {to_sha[:10]}\n"
             f"- 변경된 파일:\n{files}\n"
             f"- 변경이 이 테마의 must_cover/perspective에 해당하는 부분을 중심으로 서술한다.")
    return _writer_prompt(theme_id=theme_id, scope_block=scope,
                          origin_line=f"generated_from: {from_sha[:10]}..{to_sha[:10]}")


def init_writer_prompt(theme_id: str, unit: str, unit_files: list[str], ref: str) -> str:
    files = "\n".join(f"  - {f}" for f in unit_files[:60])
    more = f"\n  ... 외 {len(unit_files)-60}개" if len(unit_files) > 60 else ""
    scope = (f"- 모드: **최초 문서화(init)** — 변경이 아니라 현재 상태 기준\n"
             f"- 대상 단위: **{unit}** (버전 {ref[:10]})\n"
             f"- 이 단위의 소스 파일:\n{files}{more}\n"
             f"- 서드파티/외부 라이브러리로 판단되면 상세 API 문서 대신 이름·용도·통합 지점만 짧게 남긴다.")
    return _writer_prompt(theme_id=theme_id, scope_block=scope,
                          origin_line=f"generated_from: {ref[:10]} (init)")


def repo_writer_prompt(theme_id: str, repo_name: str, ref: str, summaries_block: str) -> str:
    """init reduce 단계 — 단위별 스캔 요약을 근거로 **저장소 전체** 테마 문서 합성.

    어떤 저장소든(언어·구조 무관) 레포 전체를 조망하는 문서 1편/테마. map 단계가 전체를
    훑어 만든 단위 요약들이 1차 근거이며, 특정 사실 확인이 필요할 때만 read_file로 보강한다.
    """
    scope = (f"- 모드: **최초 문서화(init, 전체 레포 스캔)** — 현재 상태 기준\n"
             f"- 대상: 저장소 **{repo_name}** 전체 (버전 {ref[:10]})\n"
             f"- 아래는 이 저장소를 단위별로 병렬 스캔한 요약이다. **이 요약들이 1차 근거다**:\n\n"
             f"{summaries_block}\n\n"
             f"- 요약을 종합해 저장소 **전체** 관점의 문서를 쓴다 — 단위를 하나씩 나열하는 게 아니라\n"
             f"  시스템 전체 그림으로 재구성한다 (레이어/역할 축으로 묶기).\n"
             f"- **고도(altitude) 규칙 — 매우 중요**: 위 단위 요약에는 클래스/함수/상수 수준의 세부가\n"
             f"  담겨 있지만, 그대로 옮기지 마라. 이 문서의 do_not_cover에 걸리는 세부(클래스 명세,\n"
             f"  설정 상수·타임아웃 값, 내부 구현 방식, 메시지 코드)는 **버리고**, 컴포넌트·모듈\n"
             f"  수준으로 추상화해 서술한다. 요약의 세부는 '무엇이 있는지 아는 근거'로만 쓴다.\n"
             f"- **수치·명칭 절제 규칙 — 매우 중요**: 버전 번호·개수·단계 수·포트 번호·기본값(ON/OFF)·\n"
             f"  연도 같은 구체 수치와, 기술 스택 구성요소 이름(라이브러리·미들웨어·프레임워크·툴킷 —\n"
             f"  예: 특정 웹서버, 특정 GUI 툴킷)은 위 요약 또는 직접 read_file로 확인한 내용에 **문자\n"
             f"  그대로** 있을 때만 쓴다. 기억·추정·일반 상식으로 만들어내지 마라 — 불확실하면 쓰지\n"
             f"  말고, 꼭 언급해야 하면 '(요약에서 확인되지 않음)'을 붙인다.\n"
             f"- **인용 경로 정직성 — 매우 중요**: frontmatter source_files와 본문의 파일/디렉터리\n"
             f"  경로는 read_file로 직접 열었거나 위 요약에 문자 그대로 등장하는 것만 쓴다. 존재를\n"
             f"  확인하지 않은 솔루션 파일·문서 경로를 만들어 넣지 말고, 디렉터리 트리를 '예상'으로\n"
             f"  그리지 마라 — critic이 경로 하나하나 실재 여부를 대조한다.\n"
             f"- **다이어그램 근거 규칙**: mermaid의 노드·엣지(의존 관계)는 요약의 '의존·통신' 항목에\n"
             f"  명시된 관계만 그린다. 그럴듯해 보여도 요약에 없는 화살표는 추가하지 마라.\n"
             f"- **mermaid 문법 규칙**: 엣지 라벨(`-->|...|`)에는 HTML 태그(`<br/>`)·괄호를 넣지 마라 —\n"
             f"  짧은 평문만. 부가 설명은 노드 라벨(`[\"...\"]` 따옴표 안)이나 본문 문장으로 옮긴다.\n"
             f"- 표를 적극 활용하라: 컴포넌트 역할 표, 기술 스택 표, 포트/의존성 표 등.\n"
             f"- 다이어그램이 must_cover에 있으면 mermaid로 그린다 (graph TB / sequenceDiagram 등).\n"
             f"- 특정 사실 확인이 필요할 때만 read_file (최대 4회). 탐색보다 종합에 집중하라.\n"
             f"- **분량: 본문 5,000~15,000자 — 상한을 넘기지 마라.** 길수록 출력이 중간에 잘릴 위험이\n"
             f"  커진다. 장황한 나열 대신 핵심 위주 — 표와 다이어그램으로 압축하라.\n"
             f"- 서드파티 라이브러리는 이름·용도·통합 지점만 짧게.")
    return _writer_prompt(theme_id=theme_id, scope_block=scope,
                          origin_line=f"generated_from: {ref[:10]} (init)")


# ── critic (검증) — Stage1(frontmatter) + Stage2(테마 적합성) + grounding ──

def critic_prompt(theme_id: str, doc_markdown: str, source_files_read: list[str]) -> str:
    read_list = "\n".join(f"  - {f}" for f in source_files_read[:40]) or "  (없음)"
    return f"""당신은 생성된 기술문서를 검증하는 엄격한 critic이다. 아래 문서를 3단계로 검증하라.
필요하면 read_file 도구로 **원본 소스를 직접 확인**해 사실 검증(grounding)을 수행하라 (최대 5회).

## 테마 정의 (검증 기준)
{theme_brief(theme_id)}

## 검증 대상 문서
```markdown
{doc_markdown[:9000]}
```

## 문서가 근거로 삼은 소스 파일
{read_list}

## Stage 1 — frontmatter 기계 검증
- theme 필드가 존재하고 `{theme_id}` 인가
- source_files 필드가 존재하고 최소 1개 항목이 있는가
- (형식이 깨졌으면 stage1=fail)

## Stage 2 — 테마 적합성 (5기준, 모두 통과해야 pass)
1. perspective: 문서 전체 관점이 테마 perspective와 부합하는가
2. do_not_cover: 금지 항목이 문서에 섞이지 않았는가
3. must_cover: 모든 항목이 다뤄졌는가
4. audience: 용어 수준·설명 깊이가 대상 독자에 맞는가
5. writing_style: 명시된 서술 방식을 따르는가

## Stage 3 — grounding 사실 검증 (원본에 없던 강화)
- 문서의 핵심 주장(클래스/함수 동작, 포트, 수치, 의존성 등)이 실제 소스와 일치하는가.
- 의심되면 read_file로 해당 파일을 확인하라. **소스에 없는데 서술된 내용(할루시네이션)**을 찾아라.

## 출력 (반드시 이 JSON만, 그 외 텍스트 금지)
{{"result": "pass|fail", "stage1_valid": true, "theme_fitness": "pass|fail", "grounding": "pass|fail", "feedback": ["라인/근거를 포함한 구체 지적 (fail 시)"]}}
result는 stage1_valid AND theme_fitness==pass AND grounding==pass 일 때만 pass.
"""
