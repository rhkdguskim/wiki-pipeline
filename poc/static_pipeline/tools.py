"""정적 파이프라인 에이전트 도구 — 전부 GitLab raw API 기반 읽기전용 코드 탐색.

에이전트가 변경 파일과 주변 코드를 탐색해 문서 근거를 모은다. 쓰기 도구는 없다.
GitLabClient·ref를 클로저로 묶어 langchain tool로 노출한다.
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool

from .gitlab_client import GitLabClient

_MAX_CHARS = 40000   # 파일 원문 잘라내기. 긴 컨텍스트 모델 전제로 넉넉히 (재-read 유발 방지)


def make_tools(client: GitLabClient, ref: str) -> list:
    """read_file / list_dir 도구를 ref(=to_sha)에 바인딩해 생성."""

    def read_file(path: str) -> str:
        """저장소의 파일 원문을 읽는다. path는 레포 루트 기준 상대경로."""
        try:
            text = client.raw_file(path, ref)
        except Exception as e:  # noqa: BLE001
            return f"[read_file 실패] {path}: {type(e).__name__}: {e}"
        if len(text) > _MAX_CHARS:
            return (text[:_MAX_CHARS] +
                    f"\n\n[...{len(text)-_MAX_CHARS}자 생략. 재요청하지 말 것 — 앞부분만으로 판단하라...]")
        return text

    def list_dir(path: str = "") -> str:
        """디렉터리의 파일·하위폴더 목록을 본다. path는 레포 루트 기준(빈 값=루트)."""
        try:
            entries = client.list_tree(path, ref)
        except Exception as e:  # noqa: BLE001
            return f"[list_dir 실패] {path}: {type(e).__name__}: {e}"
        lines = [f"{e['type']:4} {e['path']}" for e in entries]
        return "\n".join(lines) if lines else "(빈 디렉터리 또는 경로 없음)"

    return [
        StructuredTool.from_function(read_file),
        StructuredTool.from_function(list_dir),
    ]
