"""매뉴얼 테마 레지스트리 (데이터 주도) — 독자 2축.

decision-manual-taxonomy-two-reader: 산출 매뉴얼은 **독자** 기준 2축으로만 나눈다 —
사용자(작업 중심 how-to) / 운영파트·셋업자(설치·설정·트러블슈팅). 형식 축(how-to vs
레퍼런스)은 도입하지 않는다. 정적 파이프라인 themes.py와 같은 사상(데이터로 열어 확장
용이)이되, 파이프라인이 별개이므로 레지스트리도 별개다 (decision-manual-pipeline-separate).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ManualTheme:
    id: str                        # 최종 문서 frontmatter의 theme 값
    name: str                      # 사람이 읽는 이름
    audience_axis: str             # "user" | "operator" — 독자 축 (1차 분류)
    perspective: str               # 이 매뉴얼이 취하는 관점
    audience: str                  # 대상 독자 서술
    writing_style: str
    must_cover: list[str] = field(default_factory=list)
    do_not_cover: list[str] = field(default_factory=list)


MANUAL_THEMES: dict[str, ManualTheme] = {
    "user-manual": ManualTheme(
        id="manual/user-guide",
        name="사용자 매뉴얼",
        audience_axis="user",
        perspective="작업 중심 how-to — 최종 사용자가 화면에서 기능을 쓰는 방법",
        audience="최종 사용자 (이 앱으로 업무를 수행하는 사람)",
        writing_style="절차형 — 화면 단위 step-by-step, 관측된 UI 문구를 그대로 인용",
        must_cover=[
            "관측된 화면·메뉴 구조 개요 (무엇이 보이는가)",
            "주요 작업 흐름 step-by-step (무엇을 누르면 무엇이 되는가)",
            "각 절차 단계의 근거 관측 태그([oN]) 표기",
            "관측 범위와 한계 섹션 (도달하지 못한 기능 명시)",
        ],
        do_not_cover=[
            "설치·설정·배포·트러블슈팅 (→ operator-manual, 독자가 다름)",
            "내부 구현·코드·아키텍처",
            "관측되지 않은 기능의 추측 서술",
        ],
    ),
    "operator-manual": ManualTheme(
        id="manual/operator-setup",
        name="운영파트(셋업자) 매뉴얼",
        audience_axis="operator",
        perspective="설치·설정·기동·트러블슈팅 — 시스템을 세팅하고 문제를 푸는 방법",
        audience="운영/셋업 담당자 (시스템을 세팅·복구하는 사람)",
        writing_style="참조·절차 혼합형 — 설정 항목 테이블, 문제-증상-조치 표",
        must_cover=[
            "앱 실행·기동 상태 확인 방법 (관측된 범위)",
            "관측된 실행 환경·설정·연결 항목 (호스트, 포트, 리소스 등)",
            "관측된 오류·경고·대화상자와 대응 (해당 시 — 없으면 '관측되지 않음' 명시)",
            "관측 범위와 한계 섹션 (확인하지 못한 설정·절차 명시)",
        ],
        do_not_cover=[
            "최종 사용자 기능 사용법 (→ user-manual, 독자가 다름)",
            "내부 구현·코드 세부",
            "관측되지 않은 설정·절차의 추측 서술",
        ],
    ),
}

DEFAULT_MANUAL_THEMES = list(MANUAL_THEMES)


def get_manual_theme(theme_key: str) -> ManualTheme:
    if theme_key not in MANUAL_THEMES:
        raise KeyError(f"알 수 없는 매뉴얼 테마: {theme_key!r}. 등록: {list(MANUAL_THEMES)}")
    return MANUAL_THEMES[theme_key]


def manual_theme_brief(theme_key: str) -> str:
    """프롬프트에 넣을 테마 정의 블록 (정적 theme_brief와 같은 계약)."""
    t = get_manual_theme(theme_key)
    must = "\n".join(f"    - {m}" for m in t.must_cover)
    dont = "\n".join(f"    - {d}" for d in t.do_not_cover)
    return (
        f"- 테마: **{t.name}** (`{t.id}`)\n"
        f"- 독자 축(audience_axis): {t.audience_axis}\n"
        f"- 관점(perspective): {t.perspective}\n"
        f"- 대상 독자(audience): {t.audience}\n"
        f"- 서술 방식(writing_style): {t.writing_style}\n"
        f"- 반드시 다룰 것(must_cover):\n{must}\n"
        f"- 절대 다루지 말 것(do_not_cover):\n{dont}"
    )
