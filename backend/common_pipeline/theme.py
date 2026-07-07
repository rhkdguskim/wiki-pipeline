"""테마 계약 — 두 파이프라인 테마 레지스트리의 공통 스키마·프롬프트 블록.

레지스트리 **데이터**는 각 파이프라인이 소유한다 (decision-manual-pipeline-separate —
파이프라인이 별개이므로 테마 목록도 별개). 여기는 스키마(ThemeSpec)와 렌더링(brief)만
공유해 writer/critic 프롬프트가 같은 계약으로 테마를 소비하게 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThemeSpec:
    id: str                       # 최종 문서 frontmatter의 theme 값
    name: str                     # 사람이 읽는 이름
    perspective: str              # 이 문서가 취하는 관점
    audience: str                 # 대상 독자
    writing_style: str            # 서술형 / 참조형 / 절차형 ...
    must_cover: list[str] = field(default_factory=list)
    do_not_cover: list[str] = field(default_factory=list)
    section: str = ""             # 정적: 문서 섹션 (getting-started / architecture ...)
    audience_axis: str = ""       # 매뉴얼: 독자 축 (user | operator)


def lookup(registry: dict[str, ThemeSpec], key: str) -> ThemeSpec:
    if key not in registry:
        raise KeyError(f"알 수 없는 테마: {key!r}. 등록된 테마: {list(registry)}")
    return registry[key]


def brief(t: ThemeSpec) -> str:
    """프롬프트에 넣을 테마 정의 블록 (perspective·audience·style·must/do-not)."""
    must = "\n".join(f"    - {m}" for m in t.must_cover)
    dont = "\n".join(f"    - {d}" for d in t.do_not_cover)
    axis = f"- 독자 축(audience_axis): {t.audience_axis}\n" if t.audience_axis else ""
    return (
        f"- 테마: **{t.name}** (`{t.id}`)\n"
        f"{axis}"
        f"- 관점(perspective): {t.perspective}\n"
        f"- 대상 독자(audience): {t.audience}\n"
        f"- 서술 방식(writing_style): {t.writing_style}\n"
        f"- 반드시 다룰 것(must_cover):\n{must}\n"
        f"- 절대 다루지 말 것(do_not_cover):\n{dont}"
    )
