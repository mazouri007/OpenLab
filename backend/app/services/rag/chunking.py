from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.rag.document_parser import ParsedElement


TEXT_TARGET_CHARS = 1000
TEXT_HARD_LIMIT_CHARS = 1400
TEXT_MIN_CHARS = 250
TEXT_OVERLAP_CHARS = 150
PDF_TARGET_CHARS = 900
PDF_HARD_LIMIT_CHARS = 1200
PDF_MIN_CHARS = 200
TABLE_MAX_ROWS = 30
TABLE_MIN_ROWS = 3
TABLE_HARD_LIMIT_CHARS = 1600


@dataclass(slots=True)
class ChunkDraft:
    content: str
    metadata: dict[str, Any]


def chunk_elements(elements: list[ParsedElement], title: str, source_name: str | None) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    buffer: list[tuple[str, dict[str, Any]]] = []
    current_section: list[str] = []

    def flush_buffer(keep_overlap: bool = True, force: bool = False) -> None:
        nonlocal buffer
        if not buffer:
            return
        if not force and _buffer_length(buffer) < _text_min_for(buffer):
            return
        chunks.append(_build_text_chunk(buffer, title, source_name))
        buffer = _overlap_tail(buffer) if keep_overlap else []

    for element in elements:
        text = element.text.strip()
        if not text:
            continue
        if element.type == "table":
            flush_buffer(keep_overlap=False)
            chunks.extend(_chunk_table(element, title, source_name))
            buffer = []
            continue

        metadata = dict(element.metadata)
        if element.type == "heading":
            if buffer and _buffer_length(buffer) >= _text_min_for(buffer):
                flush_buffer(keep_overlap=False, force=True)
                buffer = []
            section_path = metadata.get("section_path")
            if isinstance(section_path, list):
                current_section = [str(item) for item in section_path]
            else:
                current_section = [text]
            metadata["section_path"] = current_section.copy()
            buffer.append((text, metadata))
            continue

        if current_section and not metadata.get("section_path"):
            metadata["section_path"] = current_section.copy()
        target, hard_limit = _limits_for(metadata)
        for piece in _split_large_text(text, hard_limit):
            pending_piece = piece
            while pending_piece:
                current_len = _buffer_length(buffer)
                min_chars = _min_chars_for(metadata)
                projected = _projected_length(buffer, pending_piece)
                if buffer and current_len >= min_chars and projected > target:
                    flush_buffer(keep_overlap=current_len >= TEXT_OVERLAP_CHARS)
                    continue
                if buffer and current_len < min_chars and projected > hard_limit:
                    allowance = hard_limit - current_len - 2
                    if allowance <= 0:
                        flush_buffer(keep_overlap=False, force=True)
                        continue
                    if allowance > 0:
                        buffer.append((pending_piece[:allowance].strip(), metadata))
                    flush_buffer(keep_overlap=False, force=True)
                    pending_piece = pending_piece[allowance:].strip()
                    continue
                buffer.append((pending_piece, metadata))
                if _buffer_length(buffer) >= hard_limit:
                    flush_buffer(force=True)
                break

    if buffer:
        flush_buffer(keep_overlap=False, force=True)
    return _dedupe_chunks(chunks)


def _build_text_chunk(
    buffer: list[tuple[str, dict[str, Any]]],
    title: str,
    source_name: str | None,
) -> ChunkDraft:
    content = "\n\n".join(text for text, _ in buffer).strip()
    metadata_items = [metadata for _, metadata in buffer]
    parser = _first_metadata_value(metadata_items, "parser") or "plain_text"
    metadata: dict[str, Any] = {
        "title": title,
        "source_name": source_name,
        "parser": parser,
        "chunk_strategy": "pdf_page_text" if parser == "pdf" else "semantic_text",
        "chunk_type": "pdf_page" if parser == "pdf" else _text_chunk_type(parser, content),
    }
    metadata.update(_source_location(metadata_items))
    section_path = _last_section_path(metadata_items)
    if section_path:
        metadata["section_path"] = section_path
    return ChunkDraft(content=content, metadata=metadata)


def _chunk_table(element: ParsedElement, title: str, source_name: str | None) -> list[ChunkDraft]:
    metadata = dict(element.metadata)
    rows = metadata.get("rows")
    headers = [str(item) for item in metadata.get("headers") or []]
    if not isinstance(rows, list) or not rows:
        return [
            ChunkDraft(
                content=element.text,
                metadata={
                    "title": title,
                    "source_name": source_name,
                    "parser": metadata.get("parser", "table"),
                    "chunk_strategy": "table_rows",
                    "chunk_type": "table",
                    **_source_location([metadata]),
                },
            )
        ]

    chunks: list[ChunkDraft] = []
    pending: list[dict[str, Any]] = []
    for row in rows:
        candidate = pending + [row]
        candidate_too_large = len(_format_table(headers, candidate, metadata)) > TABLE_HARD_LIMIT_CHARS
        candidate_too_many_rows = len(candidate) > TABLE_MAX_ROWS
        if len(pending) >= TABLE_MIN_ROWS and (candidate_too_many_rows or candidate_too_large):
            chunks.append(_build_table_chunk(headers, pending, metadata, title, source_name))
            pending = [row]
        else:
            pending = candidate
    if pending:
        chunks.append(_build_table_chunk(headers, pending, metadata, title, source_name))
    return chunks


def _build_table_chunk(
    headers: list[str],
    rows: list[dict[str, Any]],
    source_metadata: dict[str, Any],
    title: str,
    source_name: str | None,
) -> ChunkDraft:
    content = _format_table(headers, rows, source_metadata)
    row_indices = [int(row["index"]) for row in rows if str(row.get("index", "")).isdigit()]
    row_start = min(row_indices) if row_indices else None
    row_end = max(row_indices) if row_indices else None
    metadata: dict[str, Any] = {
        "title": title,
        "source_name": source_name,
        "parser": source_metadata.get("parser", "table"),
        "chunk_strategy": "table_rows",
        "chunk_type": "table",
        "headers": headers,
    }
    section_path = source_metadata.get("section_path")
    if section_path:
        metadata["section_path"] = section_path
    if source_metadata.get("sheet_name"):
        metadata["sheet_name"] = source_metadata["sheet_name"]
    if source_metadata.get("table_index"):
        metadata["table_index"] = source_metadata["table_index"]
    if row_start is not None:
        metadata["row_start"] = row_start
        metadata["row_end"] = row_end
    metadata["source_location"] = _format_source_location(metadata)
    return ChunkDraft(content=content, metadata=metadata)


def _format_table(headers: list[str], rows: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    label = metadata.get("sheet_name") or (
        f"表格 {metadata['table_index']}" if metadata.get("table_index") else "表格"
    )
    lines = [f"表格：{label}"]
    if headers:
        lines.append("列：" + " | ".join(headers))
    for row in rows:
        values = [str(value) for value in row.get("values", [])]
        lines.append(f"第 {row.get('index')} 行：" + _format_row(headers, values))
    return "\n".join(lines)


def _split_large_text(text: str, hard_limit: int) -> list[str]:
    if len(text) <= hard_limit:
        return [text]
    parts = [part.strip() for part in re.split(r"(?<=[。！？.!?])\s+|\n+", text) if part.strip()]
    if len(parts) <= 1:
        return [text[index : index + hard_limit].strip() for index in range(0, len(text), hard_limit)]

    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(part) > hard_limit:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(part[index : index + hard_limit].strip() for index in range(0, len(part), hard_limit))
            continue
        candidate = f"{current} {part}".strip()
        if current and len(candidate) > hard_limit:
            chunks.append(current.strip())
            current = part
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks


def _limits_for(metadata: dict[str, Any]) -> tuple[int, int]:
    if metadata.get("parser") == "pdf":
        return PDF_TARGET_CHARS, PDF_HARD_LIMIT_CHARS
    return TEXT_TARGET_CHARS, TEXT_HARD_LIMIT_CHARS


def _min_chars_for(metadata: dict[str, Any]) -> int:
    if metadata.get("parser") == "pdf":
        return PDF_MIN_CHARS
    return TEXT_MIN_CHARS


def _text_min_for(buffer: list[tuple[str, dict[str, Any]]]) -> int:
    metadata = buffer[-1][1] if buffer else {}
    return _min_chars_for(metadata)


def _overlap_tail(buffer: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    tail: list[tuple[str, dict[str, Any]]] = []
    length = 0
    for text, metadata in reversed(buffer):
        if len(text) > TEXT_OVERLAP_CHARS:
            break
        if tail and length + len(text) > TEXT_OVERLAP_CHARS:
            break
        tail.insert(0, (text, metadata))
        length += len(text)
    return tail


def _buffer_length(buffer: list[tuple[str, dict[str, Any]]]) -> int:
    if not buffer:
        return 0
    return sum(len(text) for text, _ in buffer) + (len(buffer) - 1) * 2


def _projected_length(buffer: list[tuple[str, dict[str, Any]]], next_text: str) -> int:
    if not buffer:
        return len(next_text)
    return _buffer_length(buffer) + 2 + len(next_text)


def _source_location(metadata_items: list[dict[str, Any]]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    page_starts = [_as_int(item.get("page_start")) for item in metadata_items]
    page_ends = [_as_int(item.get("page_end")) for item in metadata_items]
    page_starts = [item for item in page_starts if item is not None]
    page_ends = [item for item in page_ends if item is not None]
    if page_starts:
        metadata["page_start"] = min(page_starts)
        metadata["page_end"] = max(page_ends or page_starts)
    sheet_name = _first_metadata_value(metadata_items, "sheet_name")
    if sheet_name:
        metadata["sheet_name"] = sheet_name
    row_starts = [_as_int(item.get("row_start")) for item in metadata_items]
    row_ends = [_as_int(item.get("row_end")) for item in metadata_items]
    row_starts = [item for item in row_starts if item is not None]
    row_ends = [item for item in row_ends if item is not None]
    if row_starts:
        metadata["row_start"] = min(row_starts)
        metadata["row_end"] = max(row_ends or row_starts)
    metadata["source_location"] = _format_source_location(metadata)
    return metadata


def _format_source_location(metadata: dict[str, Any]) -> str:
    if metadata.get("page_start"):
        if metadata.get("page_start") == metadata.get("page_end"):
            return f"第 {metadata['page_start']} 页"
        return f"第 {metadata['page_start']}-{metadata['page_end']} 页"
    if metadata.get("sheet_name") and metadata.get("row_start"):
        return f"{metadata['sheet_name']} 行 {metadata['row_start']}-{metadata['row_end']}"
    if metadata.get("row_start"):
        return f"行 {metadata['row_start']}-{metadata['row_end']}"
    return ""


def _format_row(headers: list[str], values: list[str]) -> str:
    cells = []
    for index, value in enumerate(values):
        header = headers[index] if index < len(headers) and headers[index] else f"列{index + 1}"
        cells.append(f"{header}：{value}")
    return "；".join(cells) + "。"


def _text_chunk_type(parser: str, content: str) -> str:
    if parser == "manual_text":
        return "manual"
    if "```" in content or re.search(r"\b(def|class|function|const|let|var)\s+\w+", content):
        return "code"
    return "text"


def _last_section_path(metadata_items: list[dict[str, Any]]) -> list[str] | None:
    for metadata in reversed(metadata_items):
        section_path = metadata.get("section_path")
        if isinstance(section_path, list) and section_path:
            return [str(item) for item in section_path]
    return None


def _first_metadata_value(metadata_items: list[dict[str, Any]], key: str) -> Any:
    for metadata in metadata_items:
        value = metadata.get(key)
        if value:
            return value
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe_chunks(chunks: list[ChunkDraft]) -> list[ChunkDraft]:
    deduped: list[ChunkDraft] = []
    seen: set[str] = set()
    for chunk in chunks:
        if chunk.content in seen:
            continue
        seen.add(chunk.content)
        deduped.append(chunk)
    return deduped
