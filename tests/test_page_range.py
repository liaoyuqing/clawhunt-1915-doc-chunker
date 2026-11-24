"""验收 3：跨页段落的 page_from、page_to 正确。"""

from __future__ import annotations

from kb.chunker import chunk


def test_cross_page_paragraph_keeps_both_pages(doc_1, config):
    """跨页段落（第 3 页起、第 4 页续）的 page_from=3 且 page_to=4。"""
    chunks = chunk(doc_1, config)
    cross = [c for c in chunks if c.heading_path == ["空间与服务", "会议室", "跨页说明"]]
    assert len(cross) == 1
    assert cross[0].page_from == 3
    assert cross[0].page_to == 4
    assert cross[0].block_seqs == [8]


def test_single_page_chunk_has_equal_bounds(doc_1, config):
    """同页段落的 page_from 与 page_to 相等。"""
    chunks = chunk(doc_1, config)
    single = [c for c in chunks if c.heading_path == ["空间与服务", "会议室", "取消规则"]]
    assert len(single) == 1
    assert single[0].page_from == 4
    assert single[0].page_to == 4


def test_three_page_paragraph_is_split_with_contiguous_ranges(doc_3, config):
    """跨三页的长段被切成三片，每片区间落在 3..5 且首尾连续。"""
    chunks = chunk(doc_3, config)
    spans = [c for c in chunks if c.heading_path == ["三页长文"]]
    assert len(spans) == 3
    assert [c.page_from for c in spans] == [3, 3, 4]
    assert [c.page_to for c in spans] == [4, 5, 5]
    assert spans[0].page_from == 3
    assert spans[-1].page_to == 5
    for left, right in zip(spans, spans[1:]):
        assert right.page_from <= left.page_to + 1
        assert right.page_from <= left.page_from or right.page_from >= left.page_from
    for item in spans:
        assert item.page_from <= item.page_to
        assert 3 <= item.page_from <= 5
        assert 3 <= item.page_to <= 5


def test_page_range_covers_all_source_blocks(doc_1, config):
    """切片的 block_seqs 递增且都属于同一个小节的来源块。"""
    chunks = chunk(doc_1, config)
    picked = [c for c in chunks if c.heading_path == ["空间与服务", "会议室", "预订规则"]]
    assert len(picked) == 4
    assert picked[0].block_seqs == [3]
    assert picked[2].block_seqs == [3, 4]
    assert picked[-1].block_seqs == [4]
    for item in picked:
        assert item.block_seqs == sorted(item.block_seqs)
        assert item.page_from == 3 and item.page_to == 3


def test_missing_page_defaults_to_first_page():
    """没有页码字段的段落按第 1 页处理，不写 None。"""
    doc = {
        "version_id": "no-page",
        "blocks": [
            {"seq": 0, "type": "heading", "text": "无页码", "level": 1},
            {"seq": 1, "type": "paragraph", "text": "这一段故意不带任何页码字段，用于校验默认值。"},
        ],
    }
    chunks = chunk(doc)
    assert len(chunks) == 1
    assert chunks[0].page_from == 1
    assert chunks[0].page_to == 1


def test_page_header_and_footer_are_skipped(doc_1, config):
    """页眉页脚不参与切片。"""
    chunks = chunk(doc_1, config)
    assert all("第 6 页" not in c.text for c in chunks)
    assert all(5 not in c.block_seqs for c in chunks)


def test_table_chunk_carries_table_page(doc_1, config):
    """表格切片沿用表格块的页码。"""
    chunks = chunk(doc_1, config)
    pieces = [c for c in chunks if c.is_table_piece]
    assert len(pieces) == 3
    for item in pieces:
        assert item.page_from == 6
        assert item.page_to == 6
        assert item.block_seqs == [23]

