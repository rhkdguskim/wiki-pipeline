"""변경 파일 집합 -> 영향 테마 산출 (규칙 기반 결정적 코드).

원 설계는 문서 frontmatter의 source_files 매핑으로 영향 테마를 좁힌다. PoC 단계에서는
기존 docs-hub 매핑이 없으므로, 확장자·경로 휴리스틱으로 테마별 관련도를 판정한다.
PoC 단순화: 판정 불가하면 전 파일 -> 전 테마 fallback.
"""
from __future__ import annotations

# 빌드 산출물·바이너리는 문서화 대상에서 제외 (실측: prebuilt/*.lib 등).
_SKIP_SUFFIX = (".lib", ".dll", ".exe", ".obj", ".pdb", ".png", ".jpg", ".ico", ".zip")
_SKIP_DIR_HINT = ("_prebuilt", "/bin/", "/obj/", "node_modules")


def filter_source_files(changed: list[str]) -> list[str]:
    """빌드 산출물·바이너리를 걸러 실제 소스만 남긴다."""
    out = []
    for p in changed:
        low = p.lower()
        if low.endswith(_SKIP_SUFFIX):
            continue
        if any(h in low for h in _SKIP_DIR_HINT):
            continue
        out.append(p)
    return out


def themes_for_changes(changed: list[str], all_themes: list[str]) -> dict[str, list[str]]:
    """테마 -> 그 테마에 관련된 변경 파일 목록.

    PoC 규칙:
    - intro / architecture-overview / component-diagram: 소스 변경이 있으면 전체가 관련(구조 서사).
    - requirements: 빌드·의존·설정 파일(매니페스트·CI·csproj·CMake 등) 변경 시.
    관련 파일이 하나도 없는 테마는 결과에서 제외(=이번 diff는 그 테마 미생성).
    """
    sources = filter_source_files(changed)
    if not sources:
        return {}

    req_hints = (
        "cmake", ".csproj", ".vcxproj", "makefile", "package.json",
        "requirements.txt", ".gitlab-ci", "dockerfile", ".sln", "vcpkg",
    )
    req_files = [f for f in sources if any(h in f.lower() for h in req_hints)]

    result: dict[str, list[str]] = {}
    for theme in all_themes:
        if theme == "requirements":
            if req_files:
                result[theme] = req_files
        else:
            # 구조/개요/컴포넌트/intro는 소스 변경 전체를 근거로.
            result[theme] = sources
    return result
