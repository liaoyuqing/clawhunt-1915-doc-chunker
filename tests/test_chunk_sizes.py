"""验收 1：除整表切片外没有切片超过 800 字；短于 300 字的切片只出现在原小节不足 300 字时。"""

from __future__ import annotations

import pytest

from kb.chunker import ChunkerConfig, chunk


def test_no_chunk_exceeds_max_len_except_whole_table(all_docs, all_chunks, config):
    """遍历全部切片：排除整表切片后，没有任何一片超过 800 字。"""
    offenders = [
        (c.chunk_id, len(c.text), c.is_whole_table)
        for c in all_chunks
        if not c.is_whole_table and len(c.text) > config.max_len
    ]
    assert offenders == [], "非整表切片超过 %d 字：%r" % (config.max_len, offenders)

    checked = [c for c in all_chunks if not c.is_whole_table]
    assert len(checked) == 28
    assert max(len(c.text) for c in checked) == 745


def test_whole_table_may_exceed_max_len(all_chunks, config):
    """整表切片是唯一允许超过 800 字的情形。"""
    whole = [c for c in all_chunks if c.is_whole_table]
    assert len(whole) == 2
    over = [c for c in whole if len(c.text) > config.max_len]
    assert len(over) == 1
    assert len(over[0].text) == 1064
    assert over[0].heading_path == ["空间与服务", "费用与结算", "结算标准"]


def test_short_chunk_requires_short_source_section(all_docs, all_chunks, config):
    """长度小于 300 的切片，其来源小节原始长度必须也小于 300。"""
    short = [c for c in all_chunks if not c.is_table and len(c.text) < config.min_len]
    assert len(short) == 5
    for item in short:
        assert item.source_section_len < config.min_len, (
            "切片 %s 长 %d 字但来源小节有 %d 字"
            % (item.chunk_id, len(item.text), item.source_section_len)
        )
    assert sorted(len(item.text) for item in short) == [26, 26, 26, 132, 202]
    assert sorted(item.source_section_len for item in short) == [26, 26, 26, 132, 202]


def test_normal_chunks_stay_within_range(all_chunks, config):
    """原小节不短的切片，长度必须落在 [300, 800]。"""
    checked = [
        c for c in all_chunks
        if not c.is_whole_table and c.source_section_len >= config.min_len
    ]
    assert len(checked) == 23
    for item in checked:
        assert config.min_len <= len(item.text) <= config.max_len, (
            "切片 %s 长 %d 字不在 [%d, %d]"
            % (item.chunk_id, len(item.text), config.min_len, config.max_len)
        )
    assert min(len(c.text) for c in checked) == 306


def test_short_sections_are_not_merged_across_headings(doc_1, config):
    """相邻的两个短切片必须来自不同小节，证明没有跨标题合并凑长度。"""
    chunks = chunk(doc_1, config)
    short = [c for c in chunks if not c.is_table and len(c.text) < config.min_len]
    assert len(short) == 4
    for left, right in zip(short, short[1:]):
        assert left.heading_path != right.heading_path
    assert [c.heading_path[-1] for c in short] == ["跨页说明", "值班安排", "临时公告", "闭馆提醒"]
    assert len(short[2].text) + len(short[3].text) == 52 < config.min_len


def test_overlap_between_neighbour_chunks(doc_1, config):
    """同一小节内相邻切片重叠 50 字，且重叠之后长度仍不超过 800。"""
    chunks = chunk(doc_1, config)
    picked = [c for c in chunks if c.heading_path == ["空间与服务", "会议室", "预订规则"]]
    assert len(picked) == 4
    for left, right in zip(picked, picked[1:]):
        assert right.overlap_prefix_len == config.overlap
        assert right.text.startswith(left.text[-config.overlap:])
        assert len(right.text) <= config.max_len
    assert [len(c.text) for c in picked] == [570, 406, 596, 306]


def test_config_is_read_from_env():
    """KB_CHUNK_MIN / KB_CHUNK_MAX / KB_CHUNK_OVERLAP 可配置。"""
    cfg = ChunkerConfig.from_env({
        "KB_CHUNK_MIN": "200",
        "KB_CHUNK_MAX": "600",
        "KB_CHUNK_OVERLAP": "40",
        "KB_CHUNK_TABLE_MAX": "1200",
    })
    assert (cfg.min_len, cfg.max_len, cfg.overlap, cfg.table_max) == (200, 600, 40, 1200)
    assert ChunkerConfig.from_env({}).max_len == 800


def test_smaller_max_len_still_respects_limits(doc_2):
    """把上限调到 600 后，非整表切片依旧不超过 600。"""
    cfg = ChunkerConfig(min_len=200, max_len=600, overlap=40)
    chunks = chunk(doc_2, cfg)
    over = [c for c in chunks if not c.is_whole_table and len(c.text) > 600]
    assert over == []
    under = [c for c in chunks if len(c.text) < 200]
    assert under == []


def test_empty_document_yields_no_chunks():
    """空文档与小节无正文时不产出空片。"""
    assert chunk({"version_id": "empty", "blocks": []}) == []
    doc = {
        "version_id": "blank",
        "blocks": [
            {"seq": 0, "type": "heading", "text": "空小节", "level": 1},
            {"seq": 1, "type": "paragraph", "text": "   ", "page": 1},
        ],
    }
    assert chunk(doc) == []


def test_chunk_ids_are_stable(all_docs, config):
    """同一输入两次运行，chunk_id 完全一致。"""
    for doc in all_docs:
        first = [c.chunk_id for c in chunk(doc, config)]
        second = [c.chunk_id for c in chunk(doc, config)]
        assert first == second
        assert len(first) == len(set(first))
