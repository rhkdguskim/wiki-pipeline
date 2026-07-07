"""LLM 출력 텍스트 후처리 — <think> 제거·frontmatter 서문 제거·JSON 회수 (공용).

reasoning 모델이 본문에 섞는 사고 블록·내레이션을 걷어내고, "JSON만 출력하라" 지시에도
서술·펜스에 싸여 나오는 목표 JSON을 회수한다. 두 파이프라인이 같은 문제를 겪으므로
common에 있다 — 파이프라인 지식은 없다.
"""
from __future__ import annotations

import json
import re

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
_FM_BLOCK_RE = re.compile(r"^---[ \t]*\n.*?^---[ \t]*$", re.MULTILINE | re.DOTALL)
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def strip_reasoning(text: str, fm_key: str = "theme:") -> str:
    """<think> 블록 + frontmatter 앞 서문 내레이션 제거.

    writer가 "Now I have sufficient context..." 같은 내레이션을 frontmatter 앞에
    새는 경우가 있어, fm_key를 포함한 첫 frontmatter 블록부터 문서로 취급한다.
    """
    cleaned = THINK_RE.sub("", text).strip()
    for m in _FM_BLOCK_RE.finditer(cleaned):
        if fm_key in m.group(0):
            return cleaned[m.start():].strip()
    return cleaned


def extract_json_obj(text: str, key: str) -> dict:
    """주어진 key를 포함하는 JSON 오브젝트 추출 (<think>·펜스·서술 혼재 대비).

    <think> 제거본에서 먼저 찾고, 없으면 원문(=think 안에 JSON을 넣는 경우)에서 폴백.
    각 본문에서 펜스 블록 -> "key" 주변 중괄호 매칭 순으로 시도한다.
    """
    for body in (THINK_RE.sub("", text), text):
        for m in _FENCE_RE.finditer(body):
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and key in obj:
                return obj
        idx = body.find(f'"{key}"')
        if idx == -1:
            continue
        start = body.rfind("{", 0, idx)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(body)):
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(body[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and key in obj:
                        return obj
                    break
    return {}
