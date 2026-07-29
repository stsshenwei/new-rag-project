from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Literal

Strategy = Literal["auto", "heading", "heuristic", "recursive", "legacy"]
Tier = Literal["heading", "heuristic", "legacy"]

DEFAULT_SEPARATORS = ("\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; ")

MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
NUMBERED_SECTION = re.compile(r"^[ \t]*(?:\d+(?:\.\d+){1,3}\.?|(?:\d+|[IVX]{1,5})\.)[ \t]+\S.{0,200}$", re.MULTILINE)
EN_CHAPTER = re.compile(r"^[ \t]*(?:Chapter|Section|Part)\s+(?:\d+|[IVX]{1,5})[\.: ]?.{0,200}$", re.MULTILINE | re.IGNORECASE)
DE_CHAPTER = re.compile(r"^[ \t]*(?:Kapitel|Abschnitt|Teil)\s+(?:\d+|[IVX]{1,5})[\.: ]?.{0,200}$", re.MULTILINE | re.IGNORECASE)
ZH_CHAPTER = re.compile(r"^[ \t]*第[ \t]*[一二三四五六七八九十百千零〇0-9]+[ \t]*(?:章|节|篇|部分)[ \t]?.{0,200}$", re.MULTILINE)
ALL_CAPS = re.compile(r"^[ \t]*[A-ZÄÖÜ][A-ZÄÖÜ \-]{3,80}:?[ \t]*$", re.MULTILINE)
VISUAL_SEPARATOR = re.compile(r"^[ \t]*(?:-{3,}|={3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)
PAGE_FOOTER = re.compile(r"^[ \t]*(?:Seite|Page|页码?)\s+\d+(?:\s*(?:von|of|/)\s*\d+)?[ \t]*$", re.MULTILINE | re.IGNORECASE)

PROTECTED_PATTERNS = (
    re.compile(r"```[\s\S]*?```"),
    re.compile(r"\$\$[\s\S]*?\$\$"),
    re.compile(r"!\[[^\]]*\]\([^\n)]*(?:\([^)]*\)[^\n)]*)*\)"),
    re.compile(r"(?<!!)\[[^\]]+\]\([^\n)]+\)"),
    re.compile(r"(?:^[ \t]*\|[^\n]*\|[ \t]*\r?\n^[ \t]*\|[ \t]*:?-{3,}[^\n]*\|[ \t]*(?:\r?\n^[ \t]*\|[^\n]*\|[ \t]*)*)", re.MULTILINE),
)


@dataclass(frozen=True)
class TextChunk:
    content: str
    start: int
    end: int
    sequence: int
    context_header: str = ""
    strategy: str = "legacy"

    @property
    def embedding_content(self) -> str:
        body = self.content.strip()
        return f"{self.context_header}\n\n{body}" if self.context_header else body


@dataclass(frozen=True)
class DocumentProfile:
    total_chars: int
    total_lines: int
    avg_line_len: float
    std_line_len: float
    md_heading_counts: dict[int, int]
    md_heading_total: int
    numbered_section_count: int
    all_caps_short_line_count: int
    blank_paragraph_breaks: int
    form_feed_count: int
    visual_sep_count: int
    german_chapter_count: int
    english_chapter_count: int
    chinese_chapter_count: int
    repeated_footer_count: int
    has_tables: bool
    has_code: bool
    code_ratio: float
    detected_languages: tuple[str, ...]

    @property
    def heading_density(self) -> float:
        return self.md_heading_total / self.total_lines if self.total_lines else 0.0

    @property
    def heuristic_marker_total(self) -> int:
        return (
            self.numbered_section_count + self.all_caps_short_line_count + self.form_feed_count
            + self.visual_sep_count + self.german_chapter_count + self.english_chapter_count
            + self.chinese_chapter_count
        )

    def dominant_heading_level(self) -> int:
        if not self.md_heading_total:
            return 0
        for level in range(1, 7):
            if self.md_heading_counts.get(level, 0) >= 3:
                return level
        for level in range(6, 0, -1):
            if self.md_heading_counts.get(level, 0):
                return level
        return 0


@dataclass(frozen=True)
class TierRejection:
    tier: str
    reason: str


@dataclass(frozen=True)
class _SplitUnit:
    start: int
    end: int
    context_header: str = ""


@dataclass
class ChunkDiagnostics:
    selected_tier: str = "legacy"
    tier_chain: list[str] = field(default_factory=list)
    rejected: list[TierRejection] = field(default_factory=list)
    profile: DocumentProfile | None = None


@dataclass(frozen=True)
class AdaptiveChunkConfig:
    chunk_size_chars: int = 512
    chunk_overlap_chars: int = 80
    strategy: Strategy = "auto"
    separators: tuple[str, ...] = DEFAULT_SEPARATORS
    max_protected_chars: int = 7500

    def normalized(self) -> "AdaptiveChunkConfig":
        size = max(1, self.chunk_size_chars)
        overlap = max(0, min(self.chunk_overlap_chars, size // 2))
        strategy = self.strategy if self.strategy in {"auto", "heading", "heuristic", "recursive", "legacy"} else "auto"
        return AdaptiveChunkConfig(size, overlap, strategy, self.separators or DEFAULT_SEPARATORS, max(1, self.max_protected_chars))


def profile_document(text: str) -> DocumentProfile:
    lines = text.splitlines() or ([""] if text else [])
    heading_counts: dict[int, int] = {}
    lengths: list[int] = []
    in_fence = False
    code_chars = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            code_chars += len(line)
            continue
        lengths.append(len(line))
        match = MD_HEADING.match(line)
        if match:
            level = len(match.group(1))
            heading_counts[level] = heading_counts.get(level, 0) + 1
    avg = sum(lengths) / len(lengths) if lengths else 0.0
    variance = sum((value - avg) ** 2 for value in lengths) / len(lengths) if lengths else 0.0
    languages = _detect_languages(text[:4096])
    return DocumentProfile(
        total_chars=len(text), total_lines=len(lines), avg_line_len=avg, std_line_len=math.sqrt(variance),
        md_heading_counts=heading_counts, md_heading_total=sum(heading_counts.values()),
        numbered_section_count=len(NUMBERED_SECTION.findall(text)), all_caps_short_line_count=len(ALL_CAPS.findall(text)),
        blank_paragraph_breaks=text.count("\n\n\n"), form_feed_count=text.count("\f"),
        visual_sep_count=len(VISUAL_SEPARATOR.findall(text)), german_chapter_count=len(DE_CHAPTER.findall(text)),
        english_chapter_count=len(EN_CHAPTER.findall(text)), chinese_chapter_count=len(ZH_CHAPTER.findall(text)),
        repeated_footer_count=len(PAGE_FOOTER.findall(text)), has_tables=bool(re.search(r"(?m)^\s*\|.*\|\s*$", text)),
        has_code="```" in text, code_ratio=code_chars / len(text) if text else 0.0, detected_languages=languages,
    )


def select_strategy(profile: DocumentProfile) -> list[str]:
    """WeKnora invariant: eligible heading, then heuristic, always legacy."""
    chain: list[str] = []
    if profile.md_heading_total >= 3 and profile.heading_density > 0.005 and profile.dominant_heading_level() > 0:
        chain.append("heading")
    if profile.heuristic_marker_total >= 5 or profile.form_feed_count > 0 or (
        profile.german_chapter_count + profile.english_chapter_count + profile.chinese_chapter_count > 0
    ):
        chain.append("heuristic")
    chain.append("legacy")
    return chain


def validate_chunks(chunks: list[TextChunk], total_chars: int, chunk_size: int) -> tuple[bool, str]:
    if not chunks:
        return False, "no chunks produced"
    if len(chunks) == 1 and total_chars > 2 * chunk_size:
        return False, "single chunk for large document"
    lengths = [len(chunk.content) for chunk in chunks]
    tiny = sum(1 for value in lengths[:-1] if value < 50)
    if tiny > len(chunks) // 4 and tiny > 2:
        return False, "too many tiny chunks"
    if max(lengths) < chunk_size // 4 and total_chars > chunk_size:
        return False, "all chunks far below target size"
    if chunk_size > 0 and max(lengths) > 2 * chunk_size:
        return False, "chunk exceeds 2x target size"
    return True, ""


def split_with_diagnostics(text: str, config: AdaptiveChunkConfig | None = None) -> tuple[list[TextChunk], ChunkDiagnostics]:
    cfg = (config or AdaptiveChunkConfig()).normalized()
    diag = ChunkDiagnostics()
    if not text:
        return [], diag
    if cfg.strategy == "heading":
        chain, profile = ["heading", "legacy"], None
    elif cfg.strategy == "heuristic":
        chain, profile = ["heuristic", "legacy"], None
    elif cfg.strategy in {"recursive", "legacy"}:
        chain, profile = ["legacy"], None
    else:
        profile = profile_document(text)
        chain = select_strategy(profile)
    diag.tier_chain = list(chain)
    diag.profile = profile
    final: list[TextChunk] = []
    for tier in chain:
        if tier == "heading":
            output = _split_heading(text, cfg, profile)
        elif tier == "heuristic":
            output = _split_heuristic(text, cfg)
        else:
            output = _split_recursive(text, cfg)
        output = [TextChunk(c.content, c.start, c.end, i, c.context_header, tier) for i, c in enumerate(output)]
        ok, reason = validate_chunks(output, len(text), cfg.chunk_size_chars)
        if ok:
            diag.selected_tier = tier
            return output, diag
        diag.rejected.append(TierRejection(tier, reason))
        if tier == "legacy":
            final = output
    diag.selected_tier = "legacy"
    return final or _split_recursive(text, cfg), diag


def split_text(text: str, config: AdaptiveChunkConfig | None = None) -> list[TextChunk]:
    return split_with_diagnostics(text, config)[0]


def _split_heading(text: str, cfg: AdaptiveChunkConfig, profile: DocumentProfile | None) -> list[TextChunk]:
    profile = profile or profile_document(text)
    primary = profile.dominant_heading_level()
    if not primary:
        return _split_recursive(text, cfg)
    protected = _protected_spans(text)
    matches = [m for m in MD_HEADING.finditer(text) if len(m.group(1)) <= primary and not _inside(m.start(), protected)]
    if len(matches) < 2:
        return _split_recursive(text, cfg)
    starts = ([0] if matches[0].start() else []) + [m.start() for m in matches]
    starts = sorted(set(starts))
    hierarchy: list[str] = [""] * 6
    all_headings = list(MD_HEADING.finditer(text))
    chunks: list[TextChunk] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        for match in all_headings:
            if match.start() < start:
                level = len(match.group(1)); hierarchy[level - 1] = match.group(2).strip(); hierarchy[level:] = [""] * (6 - level)
            elif match.start() == start:
                level = len(match.group(1)); hierarchy[level - 1] = match.group(2).strip(); hierarchy[level:] = [""] * (6 - level)
                break
            else:
                break
        header = "\n".join(f"{'#' * (i + 1)} {value}" for i, value in enumerate(hierarchy) if value)
        section = text[start:end]
        if len(section) + len(header) + 2 <= cfg.chunk_size_chars:
            if section.strip(): chunks.append(TextChunk(section, start, end, len(chunks), header, "heading"))
        else:
            for child in _split_recursive(section, cfg):
                sub_header = _breadcrumb_at(section, child.start, header)
                chunks.append(TextChunk(child.content, start + child.start, start + child.end, len(chunks), sub_header, "heading"))
    return _coalesce_tiny(chunks, cfg.chunk_size_chars)


def _split_heuristic(text: str, cfg: AdaptiveChunkConfig) -> list[TextChunk]:
    protected = _protected_spans(text)
    candidates: dict[int, int] = {0: 100}
    patterns = ((re.compile("\f"), 100), (NUMBERED_SECTION, 90), (EN_CHAPTER, 85), (DE_CHAPTER, 85),
                (ZH_CHAPTER, 85), (ALL_CAPS, 70), (VISUAL_SEPARATOR, 60), (PAGE_FOOTER, 50), (re.compile(r"\n{3,}"), 40))
    for pattern, priority in patterns:
        for match in pattern.finditer(text):
            if not _inside(match.start(), protected):
                candidates[match.start()] = max(priority, candidates.get(match.start(), 0))
    boundaries = sorted(candidates)
    if len(boundaries) <= 1:
        return _split_recursive(text, cfg)
    chunks: list[TextChunk] = []
    current_start = boundaries[0]
    current_end = current_start
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(text)
        if end - start > cfg.chunk_size_chars:
            if current_end > current_start:
                chunks.append(TextChunk(text[current_start:current_end], current_start, current_end, len(chunks), strategy="heuristic"))
            for child in _split_recursive(text[start:end], cfg):
                chunks.append(TextChunk(child.content, start + child.start, start + child.end, len(chunks), strategy="heuristic"))
            current_start = end; current_end = end
        elif current_end > current_start and end - current_start > cfg.chunk_size_chars:
            chunks.append(TextChunk(text[current_start:current_end], current_start, current_end, len(chunks), strategy="heuristic"))
            current_start = _aligned_overlap_start(text, current_end, cfg.chunk_overlap_chars, boundaries)
            current_end = end
        else:
            current_end = end
    if current_end > current_start:
        chunks.append(TextChunk(text[current_start:current_end], current_start, current_end, len(chunks), strategy="heuristic"))
    return chunks


def _split_recursive(text: str, cfg: AdaptiveChunkConfig) -> list[TextChunk]:
    protected = _protected_spans(text)
    units: list[_SplitUnit] = []
    cursor = 0
    for start, end in protected:
        if start > cursor:
            units.extend(_as_units(_recursive_units(text, cursor, start, cfg.separators, cfg.chunk_size_chars)))
        if end - start > cfg.max_protected_chars:
            units.extend(_as_units(_hard_units(text, start, end, cfg.max_protected_chars)))
        elif _is_markdown_table(text, start, end) and end - start > cfg.chunk_size_chars:
            units.extend(_table_units(text, start, end, cfg.chunk_size_chars))
        else:
            units.append(_SplitUnit(start, end))
        cursor = end
    if cursor < len(text):
        units.extend(_as_units(_recursive_units(text, cursor, len(text), cfg.separators, cfg.chunk_size_chars)))
    chunks: list[TextChunk] = []
    start = end = 0
    for unit in units:
        if end > start and unit.end - start > cfg.chunk_size_chars:
            chunks.append(TextChunk(text[start:end], start, end, len(chunks), _context_header_for_range(text, units, start, end), "legacy"))
            start = _overlap_start(text, start, end, cfg.chunk_overlap_chars)
        if end <= start:
            start = unit.start
        end = unit.end
    if end > start:
        chunks.append(TextChunk(text[start:end], start, end, len(chunks), _context_header_for_range(text, units, start, end), "legacy"))
    return chunks


def _as_units(ranges: list[tuple[int, int]], context_header: str = "") -> list[_SplitUnit]:
    return [_SplitUnit(start, end, context_header) for start, end in ranges if end > start]


def _recursive_units(text: str, start: int, end: int, separators: tuple[str, ...], size: int) -> list[tuple[int, int]]:
    if end - start <= size: return [(start, end)] if end > start else []
    segment = text[start:end]
    for index, separator in enumerate(separators):
        points = [m.end() for m in re.finditer(re.escape(separator), segment)]
        if not points: continue
        result: list[tuple[int, int]] = []
        last = 0
        for point in points + [len(segment)]:
            if point <= last: continue
            a, b = start + last, start + point
            result.extend(_recursive_units(text, a, b, separators[index + 1 :], size) if b - a > size else [(a, b)])
            last = point
        return result
    return _hard_units(text, start, end, size)


def _hard_units(text: str, start: int, end: int, size: int) -> list[tuple[int, int]]:
    result = []
    while start < end:
        target = min(end, start + size)
        if target < end:
            window = text[start:target]
            boundary = max(window.rfind("\n"), window.rfind(" "))
            if boundary >= max(1, size - 200): target = start + boundary + 1
        result.append((start, target)); start = target
    return result


def _table_units(text: str, start: int, end: int, size: int) -> list[_SplitUnit]:
    lines = _line_spans(text, start, end)
    if len(lines) < 2:
        return [_SplitUnit(start, end)]
    separator_index = next((i for i, (_, _, line) in enumerate(lines[:3]) if _is_table_separator(line)), -1)
    if separator_index <= 0:
        return [_SplitUnit(start, end)]

    header_end = lines[separator_index][1]
    header = text[start:header_end].rstrip("\r\n")
    units: list[_SplitUnit] = []
    current_start = start
    current_end = start
    for line_start, line_end, _ in lines:
        if current_end > current_start and line_end - current_start > size:
            units.append(_SplitUnit(current_start, current_end, "" if current_start == start else header))
            current_start = line_start
            current_end = line_start
        if line_end - line_start > max(size * 2, size + len(header)):
            if current_end > current_start:
                units.append(_SplitUnit(current_start, current_end, "" if current_start == start else header))
            units.extend(_as_units(_hard_units(text, line_start, line_end, size), "" if line_start == start else header))
            current_start = line_end
            current_end = line_end
        else:
            current_end = line_end
    if current_end > current_start:
        units.append(_SplitUnit(current_start, current_end, "" if current_start == start else header))
    return units


def _line_spans(text: str, start: int, end: int) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    cursor = start
    while cursor < end:
        newline = text.find("\n", cursor, end)
        line_end = end if newline < 0 else newline + 1
        spans.append((cursor, line_end, text[cursor:line_end]))
        cursor = line_end
    return spans


def _is_markdown_table(text: str, start: int, end: int) -> bool:
    lines = [line for _, _, line in _line_spans(text, start, end)]
    return len(lines) >= 2 and _is_table_row(lines[0]) and _is_table_separator(lines[1])


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not _is_table_row(line):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _context_header_for_range(text: str, units: list[_SplitUnit], start: int, end: int) -> str:
    raw = text[start:end]
    headers: list[str] = []
    for unit in units:
        if unit.end <= start:
            continue
        if unit.start >= end:
            break
        header = unit.context_header
        if header and not raw.startswith(header) and header not in headers:
            headers.append(header)
    return "\n".join(headers)


def _protected_spans(text: str) -> list[tuple[int, int]]:
    matches = sorted((m.start(), m.end()) for pattern in PROTECTED_PATTERNS for m in pattern.finditer(text))
    result: list[tuple[int, int]] = []
    for start, end in matches:
        if not result or start >= result[-1][1]: result.append((start, end))
        elif end > result[-1][1]: result[-1] = (result[-1][0], end)
    return result


def _inside(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _overlap_start(text: str, start: int, end: int, overlap: int) -> int:
    target = max(start, end - overlap)
    newline = text.rfind("\n", max(start, end - 2 * overlap), end) if overlap else -1
    return newline + 1 if newline >= target - overlap else target


def _aligned_overlap_start(text: str, end: int, overlap: int, boundaries: list[int]) -> int:
    if overlap <= 0: return end
    floor = max(0, end - 2 * overlap)
    candidates = [value for value in boundaries if floor <= value < end]
    if candidates: return max(candidates)
    newline = text.rfind("\n", floor, max(floor, end - overlap) + 1)
    return newline + 1 if newline >= 0 else max(0, end - overlap)


def _breadcrumb_at(section: str, offset: int, initial: str) -> str:
    stack = [""] * 6
    for line in initial.splitlines():
        match = MD_HEADING.match(line)
        if match: stack[len(match.group(1)) - 1] = match.group(2).strip()
    for match in MD_HEADING.finditer(section[:offset]):
        level = len(match.group(1)); stack[level - 1] = match.group(2).strip(); stack[level:] = [""] * (6 - level)
    return "\n".join(f"{'#' * (i + 1)} {value}" for i, value in enumerate(stack) if value)


def _coalesce_tiny(chunks: list[TextChunk], size: int) -> list[TextChunk]:
    output: list[TextChunk] = []
    for chunk in chunks:
        if output and len(chunk.content) < 50 and output[-1].context_header == chunk.context_header and len(output[-1].content) + len(chunk.content) <= size:
            prior = output[-1]
            output[-1] = TextChunk(prior.content + chunk.content, prior.start, chunk.end, prior.sequence, prior.context_header, prior.strategy)
        else: output.append(chunk)
    return [TextChunk(c.content, c.start, c.end, i, c.context_header, c.strategy) for i, c in enumerate(output)]


def _detect_languages(text: str) -> tuple[str, ...]:
    if not text: return ()
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    total = max(1, cjk + latin)
    if cjk / total >= 0.15 and latin / total >= 0.15: return ("zh", "en")
    if cjk / total > 0.30: return ("zh",)
    if re.search(r"\b(?:der|die|das|und|Kapitel)\b", text, re.IGNORECASE): return ("de",)
    return ("en",)
