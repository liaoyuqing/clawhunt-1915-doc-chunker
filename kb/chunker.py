"""kb.chunker — 按标题结构的文档切片器。

纯函数、无 IO、无第三方依赖：输入解析后的文档结构（parsed_doc），输出切片列表（chunks）。

切分优先级：标题边界 → 段落 → 句子（。！？；）。
长度口径：len(text) 字符数（中文按字计）。
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

__all__ = [
    "Chunk",
    "ChunkerConfig",
    "chunk",
    "split_sentences",
    "table_lines",
    "DEFAULT_MIN_LEN",
    "DEFAULT_MAX_LEN",
    "DEFAULT_OVERLAP",
    "DEFAULT_TABLE_MAX",
]

DEFAULT_MIN_LEN = 300
DEFAULT_MAX_LEN = 800
DEFAULT_OVERLAP = 50
DEFAULT_TABLE_MAX = 1500

# 句子终止标点（不引入分词库，句子按标点规则切）
SENTENCE_DELIMITERS = "。！？；"
# 英文句读按同一套标点规则处理
ASCII_DELIMITERS = "!?;"
# 句末可能跟随的收尾符号，如 。”   』   ）
CLOSING_MARKS = "”’」』》〉】〕"

HEADING_TYPES = frozenset(["heading", "title", "section_title"])
TABLE_TYPES = frozenset(["table"])
# 页眉页脚不参与切片
SKIP_TYPES = frozenset(["header", "footer", "page_header", "page_footer"])


def _is_delimiter(ch: str) -> bool:
    return ch in SENTENCE_DELIMITERS or ch in ASCII_DELIMITERS


@dataclass(frozen=True)
class ChunkerConfig:
    """切片参数。默认值可用环境变量覆盖。"""

    min_len: int = DEFAULT_MIN_LEN
    max_len: int = DEFAULT_MAX_LEN
    overlap: int = DEFAULT_OVERLAP
    table_max: int = DEFAULT_TABLE_MAX
    prefix_heading: bool = True

    def __post_init__(self) -> None:
        if self.min_len <= 0:
            raise ValueError("min_len must be positive")
        if self.max_len < self.min_len:
            raise ValueError("max_len must not be smaller than min_len")
        if self.overlap < 0:
            raise ValueError("overlap must not be negative")
        if self.overlap >= self.min_len:
            raise ValueError("overlap must be smaller than min_len")
        if self.table_max < self.max_len:
            raise ValueError("table_max must not be smaller than max_len")

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "ChunkerConfig":
        """从环境变量读取：KB_CHUNK_MIN / KB_CHUNK_MAX / KB_CHUNK_OVERLAP /
        KB_CHUNK_TABLE_MAX / KB_PREFIX_HEADING。"""
        src = os.environ if env is None else env

        def _int(name: str, default: int) -> int:
            raw = src.get(name)
            if raw is None or str(raw).strip() == "":
                return default
            try:
                return int(str(raw).strip())
            except (TypeError, ValueError):
                return default

        def _bool(name: str, default: bool) -> bool:
            raw = src.get(name)
            if raw is None or str(raw).strip() == "":
                return default
            return str(raw).strip().lower() in ("1", "true", "yes", "on", "y")

        return cls(
            min_len=_int("KB_CHUNK_MIN", DEFAULT_MIN_LEN),
            max_len=_int("KB_CHUNK_MAX", DEFAULT_MAX_LEN),
            overlap=_int("KB_CHUNK_OVERLAP", DEFAULT_OVERLAP),
            table_max=_int("KB_CHUNK_TABLE_MAX", DEFAULT_TABLE_MAX),
            prefix_heading=_bool("KB_PREFIX_HEADING", True),
        )


@dataclass
class Chunk:
    """一个切片。长度一律按 len(text) 字符数计（中文按字计）。"""

    chunk_id: str = ""
    text: str = ""
    heading_path: List[str] = field(default_factory=list)
    page_from: int = 1
    page_to: int = 1
    block_seqs: List[int] = field(default_factory=list)
    source_section_len: int = 0
    source_unit: str = "section"
    is_table: bool = False
    is_whole_table: bool = False
    is_table_piece: bool = False
    is_short_section: bool = False
    hard_cut: bool = False
    overlap_prefix_len: int = 0
    section_index: int = 0
    prefix_heading: bool = True

    @property
    def length(self) -> int:
        return len(self.text)

    @property
    def block_seq(self) -> int:
        """来源 block 序号（切片覆盖的第一个 block）。"""
        return self.block_seqs[0] if self.block_seqs else -1

    def vector_text(self, prefix_heading: Optional[bool] = None) -> str:
        """送向量化的文本：默认在正文前拼上 heading_path（可用 prefix_heading 关闭）。

        Chunk.text 始终保持原文、不含标题前缀，便于引用回看。
        """
        use_prefix = self.prefix_heading if prefix_heading is None else prefix_heading
        if use_prefix and self.heading_path:
            return " > ".join(self.heading_path) + "\n" + self.text
        return self.text


@dataclass
class _Section:
    """一个标题小节：标题栈快照 + 其下的正文段落与表格。"""

    heading_path: List[str]
    level: int
    paragraphs: List[Tuple[Mapping[str, Any], str]]
    tables: List[Tuple[Mapping[str, Any], int]]
    index: int


def split_sentences(text: str) -> List[str]:
    """按中文标点（。！？；）切句，标点跟随前一句；不引入分词库。"""
    parts: List[str] = []
    buf: List[str] = []
    index = 0
    length = len(text)
    while index < length:
        ch = text[index]
        buf.append(ch)
        if _is_delimiter(ch):
            nxt = index + 1
            while nxt < length and (text[nxt] in CLOSING_MARKS or _is_delimiter(text[nxt])):
                buf.append(text[nxt])
                nxt += 1
            parts.append("".join(buf))
            buf = []
            index = nxt
            continue
        index += 1
    if buf:
        parts.append("".join(buf))
    return [part.strip() for part in parts if part.strip()]


def table_lines(block: Mapping[str, Any]) -> List[str]:
    """把 table block 还原成行列表；第一行即表头。"""
    rows = block.get("rows")
    if rows:
        lines: List[str] = []
        for row in rows:
            if isinstance(row, (list, tuple)):
                lines.append(" | ".join("" if cell is None else str(cell) for cell in row))
            else:
                lines.append(str(row))
        return lines
    raw = block.get("text") or ""
    return [line for line in str(raw).split("\n") if line.strip() != ""]


def _page_span(block: Mapping[str, Any]) -> Tuple[int, int]:
    """返回 block 的页码区间 (page_from, page_to)。缺页码时按第 1 页处理。"""
    start = block.get("page_start")
    end = block.get("page_end")
    if start is None:
        start = block.get("page")
    if end is None:
        end = start
    try:
        page_from = int(start)
        page_to = int(end)
    except (TypeError, ValueError):
        return 1, 1
    if page_to < page_from:
        page_to = page_from
    return page_from, page_to


def _block_seq(block: Mapping[str, Any], fallback: int) -> int:
    for key in ("seq", "block_seq", "index", "no"):
        if key in block and block[key] is not None:
            try:
                return int(block[key])
            except (TypeError, ValueError):
                continue
    return fallback


def _is_heading(block: Mapping[str, Any]) -> bool:
    return str(block.get("type", "")).strip().lower() in HEADING_TYPES


def _is_table(block: Mapping[str, Any]) -> bool:
    return str(block.get("type", "")).strip().lower() in TABLE_TYPES


def _is_skipped(block: Mapping[str, Any]) -> bool:
    return str(block.get("type", "")).strip().lower() in SKIP_TYPES


def _split_sections(blocks: Sequence[Mapping[str, Any]]) -> List[_Section]:
    """按标题边界切分小节，维护标题栈 [(level, title)]。

    规则：遇到 level <= 栈顶层级时连续弹出，直到栈顶层级小于当前 level 再压入；
    这样兄弟标题不会互相污染，跳级（1 → 3）不会补空串。
    """
    sections: List[_Section] = []
    stack: List[Tuple[int, str]] = []
    current: Optional[_Section] = None
    for position, block in enumerate(blocks):
        if _is_skipped(block):
            continue
        if _is_heading(block):
            title = str(block.get("text", "")).strip()
            try:
                level = int(block.get("level", 1) or 1)
            except (TypeError, ValueError):
                level = 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = _Section(
                heading_path=[item for _, item in stack],
                level=level,
                paragraphs=[],
                tables=[],
                index=len(sections),
            )
            sections.append(current)
            continue
        if current is None:
            # 文档首个标题之前的内容：单独成一个小节，heading_path 为空
            current = _Section(heading_path=[], level=0, paragraphs=[], tables=[], index=len(sections))
            sections.append(current)
        if _is_table(block):
            current.tables.append((block, position))
        else:
            text = str(block.get("text", "") or "")
            if text.strip():
                current.paragraphs.append((block, text))
    return sections


@dataclass
class _Prose:
    """小节正文拼接结果：内容串 + 句子边界 + 段落起点 + 来源块区间。"""

    content: str = ""
    atoms: List[Tuple[int, int]] = field(default_factory=list)
    para_starts: Set[int] = field(default_factory=set)
    blocks: List[Dict[str, Any]] = field(default_factory=list)


def _build_prose(paragraphs: Sequence[Tuple[Mapping[str, Any], str]]) -> _Prose:
    """把小节的段落拼成一个内容串，并记录句子边界、段落边界与块区间。"""
    parts: List[str] = []
    atoms: List[Tuple[int, int]] = []
    para_starts: Set[int] = set()
    blocks: List[Dict[str, Any]] = []
    offset = 0
    for position, (block, raw_text) in enumerate(paragraphs):
        if position > 0:
            parts.append("\n\n")
            offset += 2
        start = offset
        page_from, page_to = _page_span(block)
        for sentence in split_sentences(raw_text):
            atoms.append((offset, offset + len(sentence)))
            parts.append(sentence)
            offset += len(sentence)
        para_starts.add(start)
        blocks.append({
            "seq": _block_seq(block, position),
            "page_from": page_from,
            "page_to": page_to,
            "start": start,
            "end": offset,
        })
    return _Prose(content="".join(parts), atoms=atoms, para_starts=para_starts, blocks=blocks)


def _split_atoms(atoms: List[Tuple[int, int]], limit: int) -> List[Tuple[int, int]]:
    """把超长句子原子拆成不超过 limit 的等长片段（无标点可切时按字符切）。"""
    out: List[Tuple[int, int]] = []
    for start, end in atoms:
        size = end - start
        if size <= limit:
            out.append((start, end))
            continue
        pieces = int(math.ceil(size / float(limit)))
        step = int(math.ceil(size / float(pieces)))
        cursor = start
        while cursor < end:
            stop = min(cursor + step, end)
            out.append((cursor, stop))
            cursor = stop
    return out


def _plan_prose(
    content_len: int,
    atoms: List[Tuple[int, int]],
    para_starts: Set[int],
    cfg: ChunkerConfig,
) -> List[Tuple[int, int, bool]]:
    """规划正文小节的切片区间，返回 [(start, end, hard_cut)]。

    硬约束：除「整表切片」外，每片 len(text) 必须落在 [min_len, max_len]；唯一许可
    的例外是小节本身就短于 min_len（此时整节一片）。同一小节内相邻切片重叠
    overlap 字，重叠之后长度仍不得超过 max_len。

    切点优先级：段落边界 > 句子边界 > 兜底等步长（hard_cut=True）。
    """
    if content_len <= 0:
        return []
    if content_len <= cfg.max_len:
        return [(0, content_len, False)]

    overlap = cfg.overlap
    max_len = cfg.max_len
    min_len = cfg.min_len
    step = max_len - overlap
    atoms = _split_atoms(atoms, step)
    sentence_ends = {end for _, end in atoms}
    boundaries = sorted({start for start, _ in atoms} | {content_len})
    n_expected = max(2, int(math.ceil(content_len / float(step))))
    target = content_len / float(n_expected)
    memo: Dict[int, Optional[Tuple[int, ...]]] = {}

    def solve(position: int) -> Optional[Tuple[int, ...]]:
        """返回从 position 起的切点链（含终点）；None 表示该位置起无法覆盖。"""
        if position in memo:
            return memo[position]
        if position >= content_len:
            memo[position] = ()
            return memo[position]
        lo = min_len if position == 0 else min_len - overlap
        hi = max_len if position == 0 else step
        best: Optional[Tuple[Tuple[int, float, int], Tuple[int, ...]]] = None
        for candidate in boundaries:
            if candidate <= position:
                continue
            size = candidate - position
            if size < lo or size > hi:
                continue
            rest = solve(candidate)
            if rest is None:
                continue
            if candidate in para_starts:
                rank = 0
            elif candidate in sentence_ends:
                rank = 1
            else:
                rank = 2
            score = (rank, abs(size - target), -candidate)
            if best is None or score < best[0]:
                best = (score, (candidate,) + rest)
        memo[position] = best[1] if best is not None else None
        return memo[position]

    head = solve(0)
    if head is None:
        return _fallback_plan(content_len, cfg)

    cuts: List[int] = sorted({0} | set(head))
    plan: List[Tuple[int, int, bool]] = []
    for index in range(len(cuts) - 1):
        start = cuts[index] - overlap if index > 0 else 0
        end = cuts[index + 1]
        plan.append((max(0, start), end, False))
    return plan


def _fallback_plan(content_len: int, cfg: ChunkerConfig) -> List[Tuple[int, int, bool]]:
    """兜底规划：没有任何可用句子/段落边界时，按比例等步长切，仍保证区间合法。"""
    overlap = cfg.overlap
    max_len = cfg.max_len
    min_len = cfg.min_len
    step = max_len - overlap
    plan: List[Tuple[int, int, bool]] = []
    cursor = 0
    first = True
    while cursor < content_len:
        remaining = content_len - cursor
        upper = max_len if first else step
        lower = min_len if first else min_len - overlap
        if remaining <= upper:
            plan.append((max(0, cursor - overlap) if cursor else 0, content_len, True))
            break
        size = step
        rest = remaining - size
        tail_floor = min_len - overlap
        if 0 < rest < tail_floor:
            size = remaining - tail_floor
        size = max(lower, min(size, upper))
        cut = cursor + size
        plan.append((max(0, cursor - overlap) if cursor else 0, cut, True))
        cursor = cut
        first = False
    return plan


def _pages_for_span(
    blocks: Sequence[Dict[str, Any]],
    start: int,
    end: int,
) -> Tuple[int, int, List[int]]:
    """计算字符区间 [start, end) 的页码范围与覆盖的 block 序号。

    完整覆盖一个跨页 block 时直接取该 block 的精确区间（page_start / page_end）；
    只覆盖其一部分时按字符位置在 [page_start, page_end] 内插值，
    使跨页长段被切成多片时相邻区间首尾相接、不出现空洞。
    """
    page_from = None
    page_to = None
    seqs: List[int] = []
    for block in blocks:
        b_start, b_end = block["start"], block["end"]
        if b_end <= b_start:
            continue
        if b_end <= start or b_start >= end:
            continue
        sub_start = max(start, b_start)
        sub_end = min(end, b_end)
        if sub_end <= sub_start:
            continue
        p0, p1 = block["page_from"], block["page_to"]
        if p0 == p1 or (sub_start <= b_start and sub_end >= b_end):
            lo_page, hi_page = p0, p1
        else:
            size = float(b_end - b_start)
            span = float(p1 - p0)
            lo_ratio = (sub_start - b_start) / size
            hi_ratio = (sub_end - b_start) / size
            lo_page = p0 + int(math.floor(lo_ratio * span + 1e-9))
            hi_page = p0 + int(math.ceil(hi_ratio * span - 1e-9))
            lo_page = min(max(lo_page, p0), p1)
            hi_page = min(max(hi_page, lo_page), p1)
        page_from = lo_page if page_from is None else min(page_from, lo_page)
        page_to = hi_page if page_to is None else max(page_to, hi_page)
        seqs.append(block["seq"])
    if page_from is None:
        return 1, 1, seqs
    return page_from, page_to, seqs


def _pack_rows(rows: Sequence[str], capacity: int, min_body: int) -> List[List[str]]:
    """把数据行装进容量为 capacity 的若干片；行不跨行切断，末片不留过短的碎尾。"""
    if not rows:
        return []
    lengths = [len(row) + 1 for row in rows]
    total = sum(lengths)
    count = max(1, int(math.ceil(total / float(max(1, capacity)))))
    target = total / float(count)
    groups: List[List[str]] = []
    current: List[str] = []
    used = 0
    current_len = 0
    for row, size in zip(rows, lengths):
        if current and (
            used + size > capacity
            or (current_len >= target and len(groups) + 1 < count)
        ):
            groups.append(current)
            current = []
            used = 0
            current_len = 0
        current.append(row)
        used += size
        current_len += len(row)
    if current:
        groups.append(current)

    # 末片仍过短时，从上一片末尾挪行过来，保证每片正文都不低于 min_body。
    guard = 0
    while len(groups) >= 2 and guard < 64:
        guard += 1
        tail = groups[-1]
        prev = groups[-2]
        tail_len = sum(len(item) for item in tail)
        if tail_len >= min_body or len(prev) <= 1:
            break
        moved = prev.pop()
        groups[-1] = [moved] + tail
        prev_len = sum(len(item) for item in prev)
        if prev_len < min_body:
            prev.append(moved)
            groups[-1] = tail
            break
    return groups


def _table_pieces(
    block: Mapping[str, Any],
    cfg: ChunkerConfig,
) -> List[Tuple[str, bool, bool]]:
    """按表格规则生成片段，返回 [(text, is_whole_table, is_table_piece)]。

    * 表格总长 <= table_max（默认 1500）：整表一片，允许超过 max_len（唯一例外）；
    * 超过 table_max：按行拆分，每片首行都重复原表头，行不跨行切断。
    """
    lines = table_lines(block)
    if not lines:
        return []
    header = lines[0]
    body = list(lines[1:])
    joined = "\n".join(lines)
    if len(joined) <= cfg.table_max:
        return [(joined, True, False)]
    if not body:
        return [(joined, True, False)]

    capacity = cfg.max_len - len(header) - 1
    if capacity < 1:
        capacity = cfg.max_len
    min_body = max(1, cfg.min_len - len(header) - 1)

    pieces: List[Tuple[str, bool, bool]] = []
    normal: List[str] = []
    for row in body:
        if len(row) + 1 > capacity:
            # 单行本身放不进一片：该行按容量切开，每段仍带表头
            cursor = 0
            while cursor < len(row):
                stop = min(cursor + capacity, len(row))
                pieces.append((header + "\n" + row[cursor:stop], False, True))
                cursor = stop
        else:
            normal.append(row)

    for group in _pack_rows(normal, capacity, min_body):
        pieces.append((header + "\n" + "\n".join(group), False, True))
    return pieces


def chunk(
    parsed_doc: Mapping[str, Any],
    config: Optional[ChunkerConfig] = None,
    env: Optional[Mapping[str, str]] = None,
) -> List[Chunk]:
    """把解析后的文档切成切片列表。

    parsed_doc 结构（由文档解析阶段产出）：

        {
          "version_id": "v1",                            # 可选，用于生成稳定 chunk_id
          "blocks": [
            {"seq": 0, "type": "heading", "text": "空间与服务", "level": 1},
            {"seq": 1, "type": "paragraph", "text": "...", "page": 3},
            {"seq": 2, "type": "paragraph", "text": "...",
             "page_start": 3, "page_end": 4},              # 跨页段落
            {"seq": 3, "type": "table", "rows": [["表头A", "表头B"], ["值1", "值2"]]},
            {"seq": 4, "type": "header", "text": "页眉"}     # 页眉页脚跳过
          ]
        }

    纯函数：不读写文件、不联网、不修改入参。
    """
    cfg = config if config is not None else ChunkerConfig.from_env(env)
    blocks = list(parsed_doc.get("blocks") or [])
    version_id = str(parsed_doc.get("version_id", "doc"))
    sections = _split_sections(blocks)

    chunks: List[Chunk] = []
    for section in sections:
        prose = _build_prose(section.paragraphs)
        section_len = len(prose.content)
        table_len = sum(len("\n".join(table_lines(block))) for block, _ in section.tables)
        short_section = (section_len + table_len) < cfg.min_len and (section_len > 0 or table_len > 0)

        for start, end, hard in _plan_prose(section_len, prose.atoms, prose.para_starts, cfg):
            text = prose.content[start:end]
            if not text.strip():
                continue
            page_from, page_to, seqs = _pages_for_span(prose.blocks, start, end)
            chunks.append(Chunk(
                text=text,
                heading_path=list(section.heading_path),
                page_from=page_from,
                page_to=page_to,
                block_seqs=seqs,
                source_section_len=section_len,
                source_unit="section",
                is_short_section=short_section,
                hard_cut=hard,
                overlap_prefix_len=cfg.overlap if start > 0 else 0,
                section_index=section.index,
                prefix_heading=cfg.prefix_heading,
            ))

        for block, position in section.tables:
            seq = _block_seq(block, position)
            p0, p1 = _page_span(block)
            total = len("\n".join(table_lines(block)))
            for text, whole, piece in _table_pieces(block, cfg):
                if not text.strip():
                    continue
                chunks.append(Chunk(
                    text=text,
                    heading_path=list(section.heading_path),
                    page_from=p0,
                    page_to=p1,
                    block_seqs=[seq],
                    source_section_len=total,
                    source_unit="table",
                    is_table=True,
                    is_whole_table=whole,
                    is_table_piece=piece,
                    is_short_section=False,
                    hard_cut=False,
                    section_index=section.index,
                    prefix_heading=cfg.prefix_heading,
                ))

    for index, item in enumerate(chunks):
        item.chunk_id = "%s:%d:%d" % (version_id, item.block_seq, index)
    return chunks