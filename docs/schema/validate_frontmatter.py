#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
frontmatter 스키마 검증기 — wiki_pipeline LLM Wiki.

docs/wiki/ 아래 모든 지식 페이지의 YAML frontmatter가 schema.md 규약을
지키는지 검사한다. schema.md의 lint 항목 중 정적으로 판정 가능한 것을 코드화:

- 필수 4필드(type·title·tags·status) 누락
- 알 수 없는 type (라우팅 표 6종 밖)
- status enum 밖의 값 (type별 허용값)
- type↔폴더 불일치 (페이지가 자기 type 폴더 밖에 있음)
- 파일명↔type 접두사 불일치 (<type>-<slug>.md 규약)
- answered question에 blocking 태그 잔존

카탈로그 파일(index.md·*-index.md)과 루트 overview.md는 규칙에 맞게 예외 처리.
링크 무결성(깨진 링크·고아·overview 드리프트)은 별도 lint 워크플로우에서 다룬다.

종료코드: 0 = 위반 없음, 1 = 위반 있음.
스키마 SSOT는 schema.md. 이 파일의 규칙은 그 사본이므로 schema.md를 고치면 함께 고칠 것.
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# 이 스크립트는 docs/schema/ 안에 있으므로 wiki/ 는 부모(docs/) 기준.
_SCHEMA_DIR = os.path.dirname(os.path.abspath(__file__))
_DOCS = os.path.dirname(_SCHEMA_DIR)
WIKI_ROOT = os.path.join(_DOCS, "wiki")

# 지식 페이지 검사에서 제외할 wiki/ 하위 폴더 (frontmatter 없는 운영 파일)
#   log/  — 날짜별 연산 기록(append-only). frontmatter 없음.
EXCLUDED_DIRS = {"log"}

REQUIRED = {"type", "title", "tags", "status"}

# type -> (소속 폴더, 허용 status 집합)
# overview는 wiki/ 루트 고정 단일 파일(폴더 없음)
TYPES = {
    "overview":  {"folder": None,       "status": {"active"}},
    "summary":   {"folder": "summary",  "status": {"active"}},
    "entity":    {"folder": "entity",   "status": {"active"}},
    "concept":   {"folder": "concept",  "status": {"active"}},
    "decision":  {"folder": "decision", "status": {"active", "superseded"}},
    "question":  {"folder": "question", "status": {"open", "answered"}},
}


def is_catalog(fn):
    return fn == "index.md" or fn.endswith("-index.md")


def parse_fm(text):
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip()
    return fm


def main():
    violations = []
    checked = 0

    for dp, dirs, files in os.walk(WIKI_ROOT):
        # 운영 폴더(log/ 등)는 지식 페이지가 아니므로 순회에서 배제
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(dp, fn)
            rel = os.path.relpath(path, WIKI_ROOT).replace("\\", "/")
            if is_catalog(fn):
                continue  # 카탈로그 파일은 frontmatter·접두사·고아 검사 제외

            fm = parse_fm(open(path, encoding="utf-8").read())
            if fm is None:
                violations.append((rel, "frontmatter 없음 또는 파싱 불가"))
                continue

            checked += 1

            missing = REQUIRED - set(fm)
            if missing:
                violations.append((rel, f"필수 필드 누락: {sorted(missing)}"))

            t = fm.get("type")
            if t is None:
                continue
            if t not in TYPES:
                violations.append((rel, f"알 수 없는 type: {t!r} (허용: {sorted(TYPES)})"))
                continue

            spec = TYPES[t]

            # status enum
            st = fm.get("status")
            if st is not None and st not in spec["status"]:
                violations.append(
                    (rel, f"[{t}] status={st!r} 는 허용값 {sorted(spec['status'])} 밖"))

            # type↔폴더 정합
            parent = os.path.basename(os.path.dirname(path))
            if spec["folder"] is None:
                # overview: wiki/ 루트여야 함
                if os.path.dirname(path) != WIKI_ROOT:
                    violations.append((rel, f"[{t}]는 wiki/ 루트에 있어야 함"))
            else:
                if parent != spec["folder"]:
                    violations.append(
                        (rel, f"[{t}] type↔폴더 불일치: '{parent}/' 에 있으나 '{spec['folder']}/' 여야 함"))

            # 파일명 접두사 (<type>-<slug>.md). overview.md는 예외
            if t != "overview" and not fn.startswith(f"{t}-"):
                violations.append((rel, f"[{t}] 파일명 접두사 불일치: '{fn}' 은 '{t}-' 로 시작해야 함"))

            # answered question에 blocking 태그 잔존
            if t == "question" and st == "answered":
                if re.search(r"\bblocking\b", fm.get("tags", "")):
                    violations.append((rel, "answered question에 blocking 태그 잔존 (제거 필요)"))

    print(f"검사한 지식 페이지: {checked}개")
    if not violations:
        print("[OK] 스키마 위반 없음")
        return 0
    print(f"[FAIL] 위반 {len(violations)}건:\n")
    for rel, msg in sorted(violations):
        print(f"  {rel}\n    -> {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
