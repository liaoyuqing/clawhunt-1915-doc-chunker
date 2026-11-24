"""验收 4：拆分后的表格每片都带表头。"""

from __future__ import annotations

from kb.chunker import chunk, table_lines


def _table_blocks(doc):
    return [b for b in doc["blocks"] if b.get("type") == "table"]


def test_split_table_every_piece_starts_with_header(doc_1, config):
    """超长表格拆成多片，每片第一行都是原表头。"""
    table = [b for b in _table_blocks(doc_1) if b["seq"] == 23][0]
    header = table_lines(table)[0]
    assert header == "序号 | 类型 | 说明 | 标记"

    chunks = chunk(doc_1, config)
    pieces = [c for c in chunks if c.is_table_piece and c.block_seqs == [23]]
    assert len(pieces) == 3
    for item in pieces:
        lines = item.text.split("\n")
        assert lines[0] == header
        assert len(lines) >= 2
        assert item.is_whole_table is False


def test_split_table_loses_no_rows_and_duplicates_none(doc_1, config):
    """所有数据行在所有片中恰好出现一次，无丢行无重复。"""
    table = [b for b in _table_blocks(doc_1) if b["seq"] == 23][0]
    lines = table_lines(table)
    header, body = lines[0], lines[1:]
    assert len(body) == 40

    chunks = chunk(doc_1, config)
    pieces = [c for c in chunks if c.is_table_piece and c.block_seqs == [23]]
    collected = []
    for item in pieces:
        rows = item.text.split("\n")
        assert rows[0] == header
        collected.extend(rows[1:])
    assert collected == body
    assert len(collected) == len(set(collected)) == 40


def test_full_table_is_kept_as_one_piece(doc_1, config):
    """不超过 1500 字的表格整体保留为一片，标记 is_whole_table。"""
    table = [b for b in _table_blocks(doc_1) if b["seq"] == 17][0]
    lines = table_lines(table)
    total = len("\n".join(lines))
    assert total == 1064
    assert total <= config.table_max
    assert total > config.max_len

    chunks = chunk(doc_1, config)
    whole = [c for c in chunks if c.is_whole_table and c.block_seqs == [17]]
    assert len(whole) == 1
    assert whole[0].is_table is True
    assert whole[0].is_table_piece is False
    assert whole[0].text == "\n".join(lines)


def test_small_table_stays_whole(doc_3, config):
    """小表（308 字）整表一片，且长度低于 1500 的上限。"""
    chunks = chunk(doc_3, config)
    whole = [c for c in chunks if c.is_whole_table]
    assert len(whole) == 1
    assert len(whole[0].text) == 308
    assert whole[0].text.split("\n")[0] == "术语编号 | 术语 | 释义 | 备注"


def test_table_just_over_threshold_is_split(config):
    """表格总长正好超过 1500 时按行拆分，每片仍带表头。"""
    header = ["编号", "说明"]
    rows = [header]
    for index in range(1, 61):
        rows.append(["R%03d" % index, "条目 %03d 的说明文字，用于把表格撑到阈值以上。" % index])
    table = {"seq": 2, "type": "table", "page": 2, "rows": rows}
    block_text = "\n".join(" | ".join(cell for cell in row) for row in rows)
    assert len(block_text) > config.table_max

    doc = {
        "version_id": "t",
        "blocks": [
            {"seq": 0, "type": "heading", "text": "阈值校验", "level": 1},
            table,
        ],
    }
    chunks = chunk(doc, config)
    pieces = [c for c in chunks if c.is_table_piece]
    assert len(pieces) >= 2
    header_line = " | ".join(header)
    collected = []
    for item in pieces:
        lines = item.text.split("\n")
        assert lines[0] == header_line
        collected.extend(lines[1:])
    assert collected == [" | ".join(row) for row in rows[1:]]


def test_table_under_threshold_is_not_split(config):
    """表格总长小于 1500 时不做拆分。"""
    rows = [["编号", "说明"]]
    for index in range(1, 11):
        rows.append(["R%03d" % index, "短说明 %03d" % index])
    doc = {
        "version_id": "t2",
        "blocks": [
            {"seq": 0, "type": "heading", "text": "小表", "level": 1},
            {"seq": 1, "type": "table", "page": 1, "rows": rows},
        ],
    }
    chunks = chunk(doc, config)
    assert len(chunks) == 1
    assert chunks[0].is_whole_table is True


def test_every_split_piece_respects_max_len(doc_1, config):
    """拆表后的每一片都不超过 800 字（表头重复带来的额外长度已计入）。"""
    chunks = chunk(doc_1, config)
    pieces = [c for c in chunks if c.is_table_piece]
    assert len(pieces) == 3
    sizes = [len(c.text) for c in pieces]
    assert sizes == [736, 745, 641]
    assert max(sizes) <= config.max_len
