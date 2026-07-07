"""테마별 시스템 프롬프트 — 기존 Docu-Automatic 스킬 성격을 이식.

각 테마는 관점×독자로 정의된다. 에이전트는 read_file/list_dir로 근거를 모은 뒤
frontmatter 포함 마크다운 1편을 낸다. 관측된 코드 사실만 근거로 (환각 금지).
"""
from __future__ import annotations

_THEME_BRIEF = {
    "intro": "프로젝트/변경의 목적과 무엇이 바뀌었는지를 처음 보는 사람에게 소개한다.",
    "requirements": "빌드·실행에 필요한 환경·의존성·설정 조건 (독자: 설치자·운영자). "
                    "개발 환경 구성(dev-guide)과 겹치면 설치·운영 관점만 다룬다.",
    "architecture-overview": "변경이 속한 컴포넌트의 구조와 역할, 데이터·제어 흐름을 개괄한다.",
    "component-diagram": "관련 컴포넌트 간 관계를 mermaid 다이어그램과 설명으로 표현한다.",
}


def system_prompt(theme: str, changed_files: list[str], from_sha: str, to_sha: str) -> str:
    brief = _THEME_BRIEF.get(theme, f"'{theme}' 테마 문서를 작성한다.")
    files_list = "\n".join(f"  - {f}" for f in changed_files[:40])
    return f"""당신은 사내 코드 저장소의 기술문서를 작성하는 전문 기술 작가다.

## 이번 작업
- 테마: **{theme}** — {brief}
- 변경 구간: {from_sha[:10]} -> {to_sha[:10]}
- 변경된 파일:
{files_list}

## 방법 (엄격히 지켜라)
1. read_file / list_dir 도구로 변경 파일을 **최대 6회까지만** 읽어 근거를 모은다.
2. **같은 파일을 두 번 읽지 마라.** 파일이 잘려도(`[...생략...]`) 재요청하지 말고, 읽은 앞부분만으로 판단하라.
3. 도구 호출 6회에 도달했거나 근거가 충분하면 **즉시 도구를 멈추고 최종 문서를 출력**하라.
4. 코드에서 관측한 사실만 쓴다 — 추측·환각 금지. 모르면 "코드에서 확인되지 않음"이라고 쓴다.
5. 완벽한 이해보다 **문서를 완성해 내보내는 것**이 우선이다. 탐색을 무한히 하지 마라.

## 출력 형식 (반드시 이대로)
- 맨 앞에 YAML frontmatter:
---
theme: {theme}
source_files: [관련 파일 경로들]
generated_from: {from_sha[:10]}..{to_sha[:10]}
---
- 그 아래 마크다운 본문. 한국어로 작성.
- <think> 같은 사고 과정은 최종 출력에 넣지 말 것. 문서 본문만.
"""
