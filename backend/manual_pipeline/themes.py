"""매뉴얼 테마 레지스트리 (데이터 주도) — 독자 2축.

decision-manual-taxonomy-two-reader: 산출 매뉴얼은 **독자** 기준 2축으로만 나눈다 —
사용자(작업 중심 how-to) / 운영파트·셋업자(설치·설정·트러블슈팅). 형식 축(how-to vs
레퍼런스)은 도입하지 않는다. 스키마·brief 렌더링은 common_pipeline.theme 공용 계약을
쓰고 이 모듈은 데이터만 소유한다 — 파이프라인이 별개이므로 레지스트리도 별개다
(decision-manual-pipeline-separate). 정적 themes.py와 같은 모양(THEMES·DEFAULT_THEMES·
get_theme·theme_brief)이라 두 파이프라인이 같은 이름 계약으로 테마를 소비한다.
"""
from __future__ import annotations

from ..common_pipeline.theme import ThemeSpec, brief, lookup

THEMES: dict[str, ThemeSpec] = {
    "user-manual": ThemeSpec(
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
    "operator-manual": ThemeSpec(
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

DEFAULT_THEMES = list(THEMES)


def get_theme(theme_key: str) -> ThemeSpec:
    return lookup(THEMES, theme_key)


def theme_brief(theme_key: str) -> str:
    """프롬프트에 넣을 테마 정의 블록 (common_pipeline.theme.brief 렌더링)."""
    return brief(lookup(THEMES, theme_key))
