"""아티팩트 획득·배포·준비성 검사 — manual pipeline 의 PoC-후 실측 stage.

decision-artifact-consumption / decision-artifact-type-dispatch 구현:
릴리스 아티팩트(exe/msi)를 다운로드해 checksum 검증하고, MCP file_transfer 로 원격
호스트에 전송한 뒤 install/launch/readiness 를 수행한다. 각 단계 결과는 status dict
로 반환되며, runner 가 terminal failure 판정에 쓴다 (P0 review — artifact/deploy stub 제거).

설계 계약:
- 모든 단계는 예외를 raise 하지 않고 {"status": "pass"|"fail", ...} dict 를 반환한다.
  runner 는 status != "pass" 면 generation 으로 넘어가지 않고 failed 로 종료한다.
- MCP 호출은 common.McpBridge.call(name, args) -> (ok, text) 인터페이스를 쓴다.
  브리지가 관측 로그 콜백으로 모든 호출을 기록하므로(concept-observation-grounding)
  여기서 별도 로깅을 하지 않는다.
- install_profile / readiness_check / smoke_check dict 형태는 source manual profile 의
  해당 JSON 필드와 대응한다 (controlplane.services.resources._manual_profile_view).
"""
from __future__ import annotations

import hashlib
import os
from urllib.parse import urlparse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..common.mcp_bridge import McpBridge

_CHUNK = 64 * 1024
_DOWNLOAD_TIMEOUT = 180  # 초 — installer 수백 MB 대응


def download_artifact(url: str, dest: Path, expected_sha256: str = "") -> dict:
    """URL 에서 파일을 다운로드하고 checksum 을 검증한다.

    반환: {"status": "pass"|"fail", "path": str, "sha256": str, "error": str}
    - expected_sha256 이 빈 값이면 checksum 검증을 생략한다 (download-only).
    - checksum 불일치 시 다운로드 파일을 삭제하고 fail 을 반환한다.
    - urllib 가 file:// 도 지원하므로 로컬 테스트 fixture 도 그대로 쓸 수 있다.
    """
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        source_url = _normalise_file_url(url)
        digester = hashlib.sha256()
        with urllib.request.urlopen(source_url, timeout=_DOWNLOAD_TIMEOUT) as resp, \
                open(dest, "wb") as fh:
            while True:
                chunk = resp.read(_CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                digester.update(chunk)
        actual = digester.hexdigest()
        if expected_sha256 and actual.lower() != expected_sha256.lower():
            try:
                dest.unlink()
            except OSError:
                pass
            return {"status": "fail", "path": str(dest), "sha256": actual,
                    "error": (f"checksum mismatch — expected {expected_sha256}, "
                              f"got {actual}")}
        return {"status": "pass", "path": str(dest), "sha256": actual, "error": ""}
    except Exception as e:  # noqa: BLE001 — 모든 실패를 status dict 로 변환
        return {"status": "fail", "path": str(dest), "sha256": "",
                "error": f"{type(e).__name__}: {e}"}


def _normalise_file_url(url: str) -> str:
    """Accept both valid file URIs and legacy ``file://C:\\...`` test inputs."""
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return url
    if os.name != "nt":
        return url
    path_text = url[7:] if url.startswith("file://") else ""
    if not path_text:
        return url
    path_text = path_text.lstrip("/")
    if len(path_text) >= 2 and path_text[1] == ":":
        return Path(path_text).resolve().as_uri()
    return url


def deploy_via_mcp(bridge: "McpBridge", install_profile: dict,
                   artifact_path: Path) -> dict:
    """MCP file_transfer → install → launch 순으로 원격 배포를 수행한다.

    install_profile 키 (선택적, 기본값 내장):
      file_transfer_tool  (default "file_transfer") — 설치 파일 전송 MCP 도구
      transfer_args       추가 전송 인자 (dest_path 등)
      exec_tool           (default "terminal_exec") — install/launch 명령 실행 도구
      install_command     install 명령 ({artifact} → 원격 경로)
      launch_command      app 기동 명령 (선택)

    반환: {"status", "deploy_detail", "install_detail", "launch_detail", "error"}
    어느 단계라도 ok=False 면 status="fail" 로 종료한다.
    """
    result: dict = {"status": "pass", "deploy_detail": "",
                    "install_detail": "", "launch_detail": "", "error": ""}

    transfer_tool = install_profile.get("file_transfer_tool") or "file_transfer"
    transfer_args: dict = dict(install_profile.get("transfer_args") or {})
    transfer_args.setdefault("local_path", str(artifact_path))
    remote_path = install_profile.get("remote_path") or transfer_args.get("dest_path") or ""
    if remote_path:
        transfer_args["dest_path"] = remote_path

    ok, text = bridge.call(transfer_tool, transfer_args)
    result["deploy_detail"] = text[:800]
    if not ok:
        result["status"] = "fail"
        result["error"] = f"file_transfer 실패: {text[:300]}"
        return result

    exec_tool = install_profile.get("exec_tool") or "terminal_exec"
    install_cmd = install_profile.get("install_command") or ""
    if install_cmd:
        cmd = install_cmd.format(artifact=remote_path or str(artifact_path))
        ok, text = bridge.call(exec_tool, {"command": cmd})
        result["install_detail"] = text[:800]
        if not ok:
            result["status"] = "fail"
            result["error"] = f"install 실패: {text[:300]}"
            return result

    launch_cmd = install_profile.get("launch_command") or ""
    if launch_cmd:
        ok, text = bridge.call(exec_tool, {"command": launch_cmd})
        result["launch_detail"] = text[:800]
        if not ok:
            result["status"] = "fail"
            result["error"] = f"launch 실패: {text[:300]}"
            return result

    return result


def check_readiness(bridge: "McpBridge", readiness_check: dict) -> dict:
    """앱이 launch 됐는지 MCP probe(window_list / screen_info) 로 확인한다.

    readiness_check 키:
      tool           (default "window_list") — probe MCP 도구
      args           probe 인자 (default {})
      match_pattern  결과 텍스트에 포함되어야 할 패턴 (비우면 도구 ok 만 본다)
      expect_ok      True 면 도구 호출 성공만으로 pass (default True, 패턴 없을 때)

    반환: {"status": "pass"|"fail", "detail": str}
    """
    tool = readiness_check.get("tool") or "window_list"
    args = readiness_check.get("args") or {}
    pattern = readiness_check.get("match_pattern") or ""

    ok, text = bridge.call(tool, args)
    detail = text[:800]
    if not ok:
        return {"status": "fail", "detail": f"probe {tool} 실패: {detail}"}
    if pattern and pattern.lower() not in text.lower():
        return {"status": "fail",
                "detail": f"pattern '{pattern}' 을(를) 찾지 못함 — {detail}"}
    return {"status": "pass", "detail": detail}


def run_smoke(bridge: "McpBridge", smoke_check: dict) -> dict:
    """앱 반응성 검증용 최소 시나리오를 실행한다.

    smoke_check 키:
      steps  [{"tool": ..., "args": ...}, ...] — 모든 step 이 ok 여야 pass
      tool   단일 도구 (steps 없을 때)
      args   단일 도구 인자

    반환: {"status": "pass"|"fail", "detail": str}
    """
    steps = smoke_check.get("steps")
    if not steps:
        single_tool = smoke_check.get("tool")
        if not single_tool:
            return {"status": "pass", "detail": "smoke step 정의 없음 — 스킵"}
        steps = [{"tool": single_tool, "args": smoke_check.get("args") or {}}]

    details: list[str] = []
    for st in steps:
        tool = st.get("tool") or ""
        args = st.get("args") or {}
        if not tool:
            continue
        ok, text = bridge.call(tool, args)
        details.append(f"{tool}: {'ok' if ok else 'fail'} — {text[:200]}")
        if not ok:
            return {"status": "fail",
                    "detail": f"step {tool} 실패 — " + " | ".join(details)}
    return {"status": "pass", "detail": " | ".join(details) if details else "(no steps)"}
