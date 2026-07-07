"""테마 레지스트리 (데이터 주도).

원본 Docu-Automatic의 theme-definitions/themes/*.yaml 필드를 그대로 채택:
  id, name, section, perspective, audience, writing_style, must_cover, do_not_cover.
원본 4테마 + 위키 확장 2테마(dev-guide, api-protocol). 원본은 테마 하드코딩·확장경로
부재가 약점이었으므로(Explore 분석 §7-2), 여기서는 데이터로 열어 추가가 쉽다.

writer는 perspective/writing_style/must_cover/do_not_cover를 준수하고,
critic Stage2가 이 정의로 5기준(perspective·do_not_cover·must_cover·audience·writing_style)을 AND 검증한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Theme:
    id: str                       # 최종 문서 frontmatter의 theme 값
    name: str                     # 사람이 읽는 이름
    section: str                  # 섹션 (getting-started / architecture / ...)
    perspective: str              # 이 문서가 취하는 관점
    audience: str                 # 대상 독자
    writing_style: str            # 서술형 / 참조형 / 절차형 ...
    must_cover: list[str] = field(default_factory=list)
    do_not_cover: list[str] = field(default_factory=list)


# 원본 4테마 (themes/*.yaml 실값) + 확장 2테마.
THEMES: dict[str, Theme] = {
    "intro": Theme(
        id="getting-started/intro",
        name="개요",
        section="getting-started",
        perspective="프로젝트 전체 소개 — 무엇이고 왜 필요한지",
        audience="모든 방문자 (신규 팀원, 관리자)",
        writing_style="서술형 — 평이한 소개, 핵심 정보 테이블 병행",
        must_cover=[
            "시스템/제품 소개 (목적과 필요성)",
            "주요 컴포넌트·모듈 역할 요약",
            "기술 스택 개요",
            "지원 플랫폼",
        ],
        do_not_cover=[
            "개별 제품 상세 기능 명세",
            "설치·실행 방법",
            "내부 구현 세부사항",
        ],
    ),
    "requirements": Theme(
        id="getting-started/requirements",
        name="시스템 요구사항",
        section="getting-started",
        perspective="설치/실행에 필요한 환경과 조건",
        audience="설치자, 운영자",
        writing_style="참조형 — 제품별 테이블, 간결한 설명",
        must_cover=[
            "실행 환경 (OS/런타임/메모리/권한)",
            "네트워크 포트 목록 (해당 시)",
            "서드파티 의존성",
        ],
        do_not_cover=[
            "설치 절차 (→ installation)",
            "사용 방법 (→ quick-start)",
            "내부 구현 세부사항",
            "소스에서 빌드·개발하는 환경 (→ dev-guide)",
        ],
    ),
    "architecture-overview": Theme(
        id="architecture/overview",
        name="제품 아키텍처",
        section="architecture",
        perspective="시스템 전체 구조와 모듈 간 관계",
        audience="신규 팀원, 개발자",
        writing_style="서술형 — 전체 그림 중심, 다이어그램 포함",
        must_cover=[
            "Mermaid 기반 시스템 전체 구조",
            "Mermaid 기반 모듈 간 관계·통신·호출 흐름",
            "핵심 프로토콜·기술 (해당 시)",
        ],
        do_not_cover=[
            "개별 제품 내부 아키텍처 (→ tech-spec)",
            "설정 파라미터 (→ config)",
            "API 상세 명세 (→ api)",
        ],
    ),
    "component-diagram": Theme(
        id="architecture/component-diagram",
        name="컴포넌트 다이어그램",
        section="architecture",
        perspective="S/W별 대략적인 컴포넌트 구성",
        audience="개발자",
        writing_style="참조형 — 제품별 컴포넌트 테이블/다이어그램",
        must_cover=[
            "Mermaid 기반 주요 컴포넌트 (라이브러리·모듈 수준)",
            "Mermaid 기반 컴포넌트 간 의존 관계",
        ],
        do_not_cover=[
            "클래스·함수 수준 세부 (→ tech-spec)",
            "설정 파라미터 (→ config)",
        ],
    ),
    # ── 확장 (위키 decision-theme-scope-expansion) ──
    "dev-guide": Theme(
        id="development/dev-guide",
        name="개발 가이드",
        section="development",
        perspective="소스에서 빌드·테스트·디버그하며 개발하는 환경과 방법",
        audience="개발자 (이 코드에 기여하는 사람)",
        writing_style="절차형 — 단계별 안내, 명령·코드 블록 포함",
        must_cover=[
            "개발 환경 구성 (사전 요구·의존·빌드 방법)",
            "빌드/테스트/디버그 절차",
            "코드 구조와 기여 시 알아야 할 규칙 (코딩 규칙 포함)",
        ],
        do_not_cover=[
            "제품 설치·실행 환경 (→ requirements, 독자가 다름)",
            "API 상세 명세 (→ api-protocol)",
        ],
    ),
    "api-protocol": Theme(
        id="api/api-protocol",
        name="API·프로토콜",
        section="api",
        perspective="외부에서 이 시스템과 통신하는 API·프로토콜 규약",
        audience="이 시스템을 연동·호출하는 개발자",
        writing_style="명세형 — 엔드포인트·메시지·파라미터 테이블",
        must_cover=[
            "공개 API·프로토콜 엔드포인트/메시지",
            "요청·응답 형식과 파라미터",
            "인증·전송 방식 (해당 시)",
        ],
        do_not_cover=[
            "내부 구현 세부 (→ tech-spec)",
            "설치·개발 환경 (→ requirements, dev-guide)",
        ],
    ),
}

# PoC 기본 활성 테마 (원본 4 + 확장 2). 실제 활성화는 소스별 체크리스트가 결정하나
# (decision-theme-activation-checklist), PoC는 전부 켠다.
DEFAULT_THEMES = list(THEMES.keys())


def get_theme(theme_id: str) -> Theme:
    if theme_id not in THEMES:
        raise KeyError(f"알 수 없는 테마: {theme_id!r}. 등록된 테마: {list(THEMES)}")
    return THEMES[theme_id]


def theme_brief(theme_id: str) -> str:
    """프롬프트에 넣을 테마 정의 블록 (perspective·audience·style·must/do-not)."""
    t = get_theme(theme_id)
    must = "\n".join(f"    - {m}" for m in t.must_cover)
    dont = "\n".join(f"    - {d}" for d in t.do_not_cover)
    return (
        f"- 테마: **{t.name}** (`{t.id}`)\n"
        f"- 관점(perspective): {t.perspective}\n"
        f"- 대상 독자(audience): {t.audience}\n"
        f"- 서술 방식(writing_style): {t.writing_style}\n"
        f"- 반드시 다룰 것(must_cover):\n{must}\n"
        f"- 절대 다루지 말 것(do_not_cover):\n{dont}"
    )
