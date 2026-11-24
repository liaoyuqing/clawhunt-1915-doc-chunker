"""验收 2：三级嵌套标题下的 heading_path 正确。"""

from __future__ import annotations

from kb.chunker import chunk


def test_three_level_path_is_exact(doc_2, config):
    """三级嵌套：「园区导览 > 展厅与动线 > 参观预约」逐元素相等。"""
    chunks = chunk(doc_2, config)
    nested = [c for c in chunks if c.heading_path == ["园区导览", "展厅与动线", "参观预约"]]
    assert len(nested) == 2
    for item in nested:
        assert item.heading_path == ["园区导览", "展厅与动线", "参观预约"]
        assert len(item.heading_path) == 3


def test_sibling_heading_does_not_pollute_path(doc_2, config):
    """同级第二个三级标题单独成路径，兄弟标题不污染。"""
    chunks = chunk(doc_2, config)
    sibling = [c for c in chunks if c.heading_path == ["园区导览", "展厅与动线", "讲解服务"]]
    assert len(sibling) == 1
    assert sibling[0].heading_path[-1] == "讲解服务"
    assert "参观预约" not in sibling[0].heading_path


def test_back_to_level_two_truncates_path(doc_2, config):
    """回到二级标题后路径长度回到 2。"""
    chunks = chunk(doc_2, config)
    back = [c for c in chunks if c.heading_path == ["园区导览", "服务台"]]
    assert len(back) == 1
    assert len(back[0].heading_path) == 2
    deeper = [c for c in chunks if c.heading_path == ["园区导览", "服务台", "应急联络"]]
    assert len(deeper) == 1
    assert len(deeper[0].heading_path) == 3


def test_heading_level_jump_does_not_insert_empty_strings(doc_2, config):
    """一级标题后直接跳三级标题，路径长度 2，不补空串。"""
    chunks = chunk(doc_2, config)
    jumped = [c for c in chunks if c.heading_path == ["交通指引", "地铁接驳"]]
    assert len(jumped) == 1
    assert len(jumped[0].heading_path) == 2
    assert "" not in jumped[0].heading_path
    assert all(item.strip() for item in jumped[0].heading_path)


def test_document_starting_at_level_three_has_length_one(doc_3, config):
    """文档以三级标题开头且无父级时，路径长度为 1。"""
    chunks = chunk(doc_3, config)
    first = [c for c in chunks if c.heading_path == ["附录说明"]]
    assert len(first) == 1
    assert len(first[0].heading_path) == 1


def test_table_chunk_shares_section_path(doc_1, config):
    """表格切片与其所属小节使用同一条 heading_path。"""
    chunks = chunk(doc_1, config)
    table_chunks = [c for c in chunks if c.is_table]
    assert len(table_chunks) == 4
    whole = [c for c in table_chunks if c.is_whole_table][0]
    assert whole.heading_path == ["空间与服务", "费用与结算", "结算标准"]
    pieces = [c for c in table_chunks if c.is_table_piece]
    assert len(pieces) == 3
    for item in pieces:
        assert item.heading_path == ["空间与服务", "费用与结算", "明细清单"]


def test_every_chunk_carries_a_path(all_chunks):
    """所有切片都带非空的 heading_path，元素为非空字符串。"""
    for item in all_chunks:
        assert item.heading_path
        assert all(isinstance(part, str) and part for part in item.heading_path)


def test_vector_text_prepends_heading_path(doc_2, config):
    """用于向量化的文本默认拼上 heading_path，可关闭。"""
    chunks = chunk(doc_2, config)
    item = [c for c in chunks if c.heading_path == ["园区导览", "服务台"]][0]
    prefixed = item.vector_text()
    assert prefixed.startswith("园区导览 > 服务台\n")
    assert prefixed.endswith(item.text)
    assert item.vector_text(prefix_heading=False) == item.text
    assert item.text.startswith("服务台负责受理")


def test_prefix_heading_can_be_disabled_in_config(doc_3):
    """KB_PREFIX_HEADING 关闭时，向量化文本与正文一致。"""
    cfg = __import__("kb.chunker", fromlist=["ChunkerConfig"]).ChunkerConfig(prefix_heading=False)
    chunks = chunk(doc_3, cfg)
    for item in chunks:
        assert item.vector_text() == item.text
