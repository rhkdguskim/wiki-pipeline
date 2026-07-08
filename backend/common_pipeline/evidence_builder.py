"""Evidence Builder — LLM 호출 전에 근거를 구조화된 evidence pack 으로 만든다.

raw/2026-07-08-ai-agent-output-quality-plan.md §1 Evidence Builder 의 구현.
writer/critic 은 raw repository 나 raw observation JSONL 전체를 직접 받지 않고
이 모듈이 만든 bounded evidence pack 만 소비한다 — 모든 주장 가능한 근거는
evidence_id 로 참조된다.

출력은 /api/webhook/evidence 와 /api/webhook/final-pack 의 payload schema 와
일치한다 (controlplane.services.resources.upsert_evidence_pack 이 소비 가능).
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

# evidence item 1개당 content 상한 — writer/critic prompt 에 들어갈 수 있는 양.
# 길이 제한이 없으면 LLM context 가 터지거나 truncation 으로 잘린다.
MAX_ITEM_CONTENT_CHARS = 8000
# pack 전체 item 수 상한 — 너무 많으면 critic 이 모든 근거를 못 본다.
MAX_ITEMS = 200
# chunking 시 한 파일에서 만들 최대 item 수 — 그 이상은 omitted_count 로.
MAX_CHUNKS_PER_FILE = 8

_VALID_KINDS = frozenset({
    "source_file", "diff_hunk", "config", "observation",
    "screenshot", "scenario", "coverage",
})


def _make_pack_id(run_id: str, pipeline_id: str, version_ref: str) -> str:
    """run_id·pipeline_id·version_ref 기반 deterministic pack_id.

    같은 입력에 같은 pack_id 가 나와야 run 간 비교·중복 제거가 된다
    (raw 설계서 'Stable IDs' 참조).
    """
    digest = hashlib.sha1(
        f"{pipeline_id}|{run_id}|{version_ref}".encode("utf-8"),
    ).hexdigest()[:12]
    return f"evpack-{digest}"


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    """text 를 limit 자로 자르고 잘렸는지 여부를 반환."""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _chunk_long_content(
    item: dict, *, chunk_size: int, max_chunks: int,
) -> tuple[list[dict], int]:
    """긴 content 를 줄 단위로 chunk_size 에 맞춰 여러 evidence item 으로 쪼갠다.

    같은 id 접두사에 -c1, -c2 ... 접미사를 붙여 파생 item id 를 만든다.
    원본 item 의 path/kind/metadata 는 그대로 계승하고, line_start/line_end 를
    chunk 경계로 채운다 (caller 가 안 줬을 때만). 반환: (chunk_items, omitted).
    """
    content = item.get("content") or ""
    if len(content) <= chunk_size:
        return [item], 0

    lines = content.splitlines(keepends=True)
    # 단일 라인이 chunk_size 를 넘으면 문자 단위로 강제 분할 (개행 없는 긴 파일 대비).
    forced_lines: list[str] = []
    for ln in lines:
        while len(ln) > chunk_size:
            forced_lines.append(ln[:chunk_size])
            ln = ln[chunk_size:]
        if ln:
            forced_lines.append(ln)
    if forced_lines:
        lines = forced_lines

    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for ln in lines:
        if cur_len + len(ln) > chunk_size and cur:
            chunks.append("".join(cur))
            cur, cur_len = [], 0
        cur.append(ln)
        cur_len += len(ln)
    if cur:
        chunks.append("".join(cur))

    base_id = item.get("id") or f"evi-{uuid.uuid4().hex[:8]}"
    base_path = item.get("path") or ""
    kind = item.get("kind") or "source_file"
    title = item.get("title") or ""
    metadata = item.get("metadata") or {}

    omitted = max(0, len(chunks) - max_chunks)
    chunks = chunks[:max_chunks]

    out: list[dict] = []
    base_line = item.get("line_start") or 1
    for i, chunk_text in enumerate(chunks, 1):
        n_lines = chunk_text.count("\n")
        out.append({
            "id": f"{base_id}-c{i}" if len(chunks) > 1 else base_id,
            "kind": kind,
            "path": base_path,
            "title": f"{title} (chunk {i}/{len(chunks)})" if len(chunks) > 1 else title,
            "content": chunk_text,
            "content_preview": chunk_text[:16000],
            "line_start": base_line if "line_start" not in item else item["line_start"],
            "line_end": base_line + n_lines - 1 if "line_end" not in item else item["line_end"],
            "metadata": {**metadata, "chunk_index": i, "chunk_total": len(chunks)},
        })
        base_line += n_lines
    return out, omitted


def build_evidence_pack(
    run_id: str,
    source_id: str,
    pipeline_id: str,
    version_ref: str,
    items: list[dict],
    *,
    max_item_chars: int = MAX_ITEM_CONTENT_CHARS,
    max_items: int = MAX_ITEMS,
    max_chunks_per_file: int = MAX_CHUNKS_PER_FILE,
) -> dict:
    """raw items 를 bounded evidence pack 으로 증류.

    입력 item 스키마 (raw/ 설계서 §1):
      id, kind, path, title, content, metadata (optional line_start/line_end)

    출력 dict 는 webhook payload schema 와 호환:
      pack_id, run_id, source_id, pipeline_id, version_ref,
      item_count, source_file_count, observation_count, unsupported_claim_count,
      truncated, omitted_count, items[]

    규칙:
    - kind 가 _VALID_KINDS 밖이면 'source_file' 으로 정규화 (버리지 않는다).
    - 긴 content 는 chunk 단위로 분할 (같은 id 접두사 + -cN 접미사).
    - max_items 초과 분은 omitted_count 로 보고하고 버린다.
    """
    pack_id = _make_pack_id(run_id, pipeline_id, version_ref)

    expanded: list[dict] = []
    truncated_any = False
    omitted_total = 0

    for raw_item in items or []:
        if not isinstance(raw_item, dict):
            continue
        kind = raw_item.get("kind") or "source_file"
        if kind not in _VALID_KINDS:
            kind = "source_file"

        # chunking 이 먼저다 — 긴 content 는 자르지 않고 여러 item 으로 분할.
        # truncation 은 chunk 한도(max_chunks_per_file) 초과 시에만 발생한다.
        raw_content = raw_item.get("content") or ""
        if not isinstance(raw_content, str):
            raw_content = str(raw_content) if raw_content is not None else ""

        normalized = {
            "id": str(raw_item.get("id") or f"evi-{uuid.uuid4().hex[:10]}"),
            "kind": kind,
            "path": str(raw_item.get("path") or ""),
            "title": str(raw_item.get("title") or ""),
            "content": raw_content,
            "metadata": raw_item.get("metadata") if isinstance(
                raw_item.get("metadata"), dict) else {},
        }
        for k in ("line_start", "line_end", "observation_id",
                  "scenario_id", "artifact_ref", "content_uri"):
            if k in raw_item and raw_item[k] is not None:
                normalized[k] = raw_item[k]

        chunks, omitted = _chunk_long_content(
            normalized,
            chunk_size=max_item_chars,
            max_chunks=max_chunks_per_file,
        )
        if omitted > 0:
            truncated_any = True
        expanded.extend(chunks)
        omitted_total += omitted

    # 전체 item 수 상한 — 초과분은 omitted 로.
    if len(expanded) > max_items:
        omitted_total += len(expanded) - max_items
        expanded = expanded[:max_items]
        truncated_any = True

    # webhook payload 용 count 집계 — source_file/observation kind 별 count.
    source_file_count = sum(1 for it in expanded if it.get("kind") == "source_file")
    observation_count = sum(1 for it in expanded if it.get("kind") == "observation")

    # content_preview 는 webhook 저장 시 16KB 로 추가 잘리지만, payload 에는 미리 채워둔다.
    for it in expanded:
        if "content_preview" not in it:
            it["content_preview"] = (it.get("content") or "")[:16000]

    return {
        "pack_id": pack_id,
        "evidence_id": pack_id,  # 설계서 schema 호환 (동의어)
        "run_id": run_id,
        "source_id": source_id,
        "pipeline_id": pipeline_id,
        "version_ref": str(version_ref or "")[:120],
        "item_count": len(expanded),
        "source_file_count": source_file_count,
        "observation_count": observation_count,
        "unsupported_claim_count": 0,  # critic 단계에서 채움 — 기본 0
        "truncated": truncated_any,
        "omitted_count": omitted_total,
        "items": expanded,
        "limits": {
            "truncated": truncated_any,
            "omitted_count": omitted_total,
            "max_item_chars": max_item_chars,
            "max_items": max_items,
        },
    }


def evidence_block_text(pack: dict, *, max_chars: int = 60000) -> str:
    """evidence pack 을 writer/critic prompt 에 넣을 텍스트 블록으로 직렬화.

    [id|kind] path — title
    <content 앞부분>

    pack.items 의 content 를 합쳐 하나의 근거 블록을 만든다. 길면 max_chars 로
    자르되 head:tail 비율 60:35 로 양끝을 보존한다 (observation.evidence_block 패턴).
    """
    items = pack.get("items") or []
    if not items:
        return "(근거 없음)"

    def _render(cut: int | None) -> str:
        lines = []
        for it in items:
            header = f"[{it.get('id')}|{it.get('kind')}]"
            if it.get("path"):
                header += f" {it['path']}"
            if it.get("title"):
                header += f" — {it['title']}"
            content = it.get("content") or ""
            if cut is not None:
                content = content[:cut]
            lines.append(f"{header}\n{content}")
        return "\n\n".join(lines)

    block = _render(None)
    if len(block) <= max_chars:
        return block
    # 1차: content 만 줄여서 재시도
    block = _render(2000)
    if len(block) <= max_chars:
        return block
    # 2차: 양끝 보존 단절
    head = block[: int(max_chars * 0.6)]
    tail = block[-int(max_chars * 0.35):]
    return (
        head
        + "\n\n[...중략: 근거가 길어 일부 생략...]\n\n"
        + tail
    )


def evidence_ids(pack: dict) -> list[str]:
    """pack 에서 사용 가능한 evidence id 목록을 반환 (critic grounding 용)."""
    return [str(it.get("id")) for it in (pack.get("items") or []) if it.get("id")]
