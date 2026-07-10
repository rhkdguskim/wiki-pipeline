"""변경 파일 집합 -> 영향 테마 산출 (규칙 기반 결정적 코드).

원 설계는 문서 frontmatter의 source_files 매핑으로 영향 테마를 좁힌다. PoC 단계에서는
기존 docs-hub 매핑이 없으므로, 확장자·경로 휴리스틱으로 테마별 관련도를 판정한다.
PoC 단순화: 판정 불가하면 전 파일 -> 전 테마 fallback.
"""
from __future__ import annotations

import re

# 빌드 산출물·바이너리는 문서화 대상에서 제외 (실측: prebuilt/*.lib 등).
_SKIP_SUFFIX = (".lib", ".dll", ".exe", ".obj", ".pdb", ".png", ".jpg", ".ico", ".zip")
_SKIP_DIR_HINT = ("_prebuilt", "/bin/", "/obj/", "node_modules")

# 서드파티/vendored 라이브러리는 우리 코드가 아니므로 문서화 제외.
# 경로 세그먼트 단위로 매칭 (예: "Src/3rdparty/..." -> "3rdparty" 세그먼트).
_VENDORED_SEGMENTS = {
    "3rdparty", "third_party", "thirdparty", "vendor", "vendored",
    "external", "extern", "deps", "dependencies", "packages",
    "node_modules", "submodules",
}


def is_vendored(path: str) -> bool:
    """경로에 서드파티/외부 라이브러리 디렉터리 세그먼트가 있으면 True."""
    segs = [s.lower() for s in path.replace("\\", "/").split("/")]
    return any(s in _VENDORED_SEGMENTS for s in segs)


# .gitmodules 의 `path = <dir>` 라인에서 서브모듈 경로를 뽑는다.
_SUBMODULE_PATH_RE = re.compile(r"(?m)^\s*path\s*=\s*(.+?)\s*$")


def parse_submodule_paths(gitmodules_text: str) -> list[str]:
    """.gitmodules 원문에서 서브모듈 경로 목록을 파싱한다 (없으면 빈 리스트).

    서브모듈은 우리 코드가 아니므로 문서화 대상에서 제외한다 (사용자 요구:
    "서브모듈은 참고하지 않는다"). git 트리에서 서브모듈은 gitlink(type=commit)라
    blob 필터로 대부분 걸러지지만, .gitmodules 로 경로를 명시적으로 배제해 확실히 한다.
    """
    if not gitmodules_text:
        return []
    return [m.strip().replace("\\", "/").rstrip("/")
            for m in _SUBMODULE_PATH_RE.findall(gitmodules_text) if m.strip()]


def under_any(path: str, roots: list[str]) -> bool:
    """path 가 roots 중 하나와 같거나 그 하위이면 True (서브모듈 경로 배제용)."""
    p = path.replace("\\", "/")
    for r in roots:
        r = r.replace("\\", "/").rstrip("/")
        if r and (p == r or p.startswith(r + "/")):
            return True
    return False


def filter_source_files(changed: list[str]) -> list[str]:
    """빌드 산출물·바이너리·서드파티를 걸러 우리 소스만 남긴다."""
    out = []
    for p in changed:
        low = p.lower()
        if low.endswith(_SKIP_SUFFIX):
            continue
        if any(h in low for h in _SKIP_DIR_HINT):
            continue
        if is_vendored(p):
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

    build_hints = (
        "cmake", ".csproj", ".vcxproj", "makefile", "package.json",
        "requirements.txt", ".gitlab-ci", "dockerfile", ".sln", "vcpkg",
    )
    api_hints = (
        "api", "protocol", "endpoint", "handler", "route", "controller",
        "dispatcher", ".proto", "swagger", "openapi", "rpc",
    )
    build_files = [f for f in sources if any(h in f.lower() for h in build_hints)]
    api_files = [f for f in sources if any(h in f.lower() for h in api_hints)]

    result: dict[str, list[str]] = {}
    for theme in all_themes:
        if theme == "requirements":
            if build_files:
                result[theme] = build_files
        elif theme == "dev-guide":
            # 빌드/개발 환경 관련 파일 변경 시.
            if build_files:
                result[theme] = build_files
        elif theme == "api-protocol":
            # API/프로토콜성 파일 변경 시에만 (opt-in 성격).
            if api_files:
                result[theme] = api_files
        else:
            # intro / architecture-overview / component-diagram: 소스 변경 전체를 근거로.
            result[theme] = sources
    return result
