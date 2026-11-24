# 按标题结构的文档切片器（S3-KB-011）

把解析后的文档切成「能进向量库、又能被引用回原位」的切片。切分顺序：**标题边界 → 段落 → 句子（。！？；）**。纯函数、无 IO、不联网、不引入分词库。

## 1. 运行环境与依赖

| 项 | 要求 |
| --- | --- |
| Python | 3.11 及以上（本仓库在 3.11.9 与 3.12.10 上实跑通过） |
| 运行依赖 | 无（仅标准库：`dataclasses`、`math`、`os`、`typing`） |
| 测试依赖 | `pytest`（唯一第三方包） |
| 不引入 | 分词库、向量库、网络客户端、PDF/Word 解析器 |

```bash
git clone https://github.com/liaoyuqing/clawhunt-1915-doc-chunker.git
cd clawhunt-1915-doc-chunker
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

预期输出：`33 passed`。

统计脚本：

```bash
python scripts/chunk_stats.py
```

## 2. 目录

```
kb/chunker.py            切片器本体：chunk(parsed_doc) -> list[Chunk]
samples/doc_1.json       虚构样例一：三级标题、跨页段落、整表与拆表、超短小节
samples/doc_2.json       虚构样例二：三级嵌套、兄弟标题、跳级标题
samples/doc_3.json       虚构样例三：跨三页长段、以三级标题开头的文档、短小节
scripts/make_samples.py  重新生成三个样例（内容全部虚构）
scripts/chunk_stats.py   切片数、长度分布、重叠率、表格片数统计
tests/                   四组验收用例 + 公共夹具
```

## 3. 输入结构（parsed_doc）

```python
{
  "version_id": "doc-1",                       # 可选，用于生成稳定 chunk_id
  "blocks": [
    {"seq": 0, "type": "heading",   "text": "空间与服务", "level": 1},
    {"seq": 1, "type": "paragraph", "text": "...", "page": 3},
    {"seq": 2, "type": "paragraph", "text": "...",
     "page_start": 3, "page_end": 4},           # 跨页段落
    {"seq": 3, "type": "table",     "rows": [["表头A", "表头B"], ["值1", "值2"]]},
    {"seq": 4, "type": "header",    "text": "页眉"}   # 页眉页脚跳过
  ]
}
```

`type` 取值：`heading` / `paragraph` / `table`，以及被跳过的 `header`、`footer`。
页码字段依次尝试 `page_start`+`page_end`，再退到 `page`，都没有时按第 1 页处理。

## 4. 输出结构（Chunk）

| 字段 | 含义 |
| --- | --- |
| `text` | 切片正文。**不含标题前缀**，长度一律按 `len(text)` 字符数计（中文按字计） |
| `heading_path` | 标题数组，如 `["空间与服务", "会议室", "预订规则"]` |
| `page_from` / `page_to` | 覆盖的起始页与结束页；同页时两值相等 |
| `block_seqs` | 覆盖的来源 block 序号（升序）；`block_seq` 属性给出第一个 |
| `source_section_len` | 来源小节的原始字符长度（用于判定短切片是否合法） |
| `is_whole_table` | 整表成片标记（唯一允许超过 `max_len` 的切片） |
| `is_table_piece` | 拆表后的表格片标记 |
| `is_short_section` | 来源小节本身就短于 `min_len` |
| `hard_cut` | 切点不在句子/段落边界上（样例数据上未触发） |
| `overlap_prefix_len` | 本片开头从上一片借来的字符数（小节内首片为 0） |
| `vector_text()` | 送向量化的文本：默认拼上 `heading_path.join(" > ")`，可关 |

## 5. 切分规则

**5.1 标题栈。** 遍历 block 时维护 `[(level, title)]`：遇到 `level <= 栈顶` 连续弹出，直到栈顶层级小于当前层级再压入。因此兄弟标题不污染、跳级（1 → 3）不补空串、回到二级后路径长度回到 2。文档以三级标题开头时路径长度为 1。

**5.2 小节内切片。** 同一小节内的段落拼成一个内容串，句子边界来自标点规则；

- 整节 `<= max_len`：整节一片；
- 否则在句子/段落边界上做动态规划，约束每片 `len(text)` 落在 `[min_len, max_len]`，
  相邻两片共享 `overlap` 字（后一片开头 = 前一片结尾 `overlap` 字），**重叠算进长度**，不额外加长；
- 切点优先落在段落边界，其次句子边界；两者都不可行才按等步长硬切并标 `hard_cut=True`。

**5.3 短小节不合并。** 小节本身不足 `min_len` 时单独成片（`is_short_section=True`），**不跨标题合并凑长度**。判定依据是 `source_section_len`，不是切片长度。

**5.4 表格。**

- 表格总长 `<= table_max`（1500）：整表一片，`is_whole_table=True`，允许超过 `max_len`；
- 超过阈值：按行拆，**每片首行都重复原表头**，行不跨行切断；单行本身放不进一片时按容量切行，每段仍带表头；
- 拆出的片同样受 `max_len` 约束（表头长度已计入）。

**5.5 页码。** 完整覆盖一个跨页 block 时直接取该块的 `page_start`/`page_end`；只覆盖其一的一部分时按字符位置在区间内插值，保证跨三页的长段切成三片时页码范围连续、无空洞。

**5.6 确定性。** `chunk_id` 形如 `{version_id}:{block_seq}:{idx}`，同一输入两次运行结果完全一致。

## 6. 可配置开关（环境变量）

| 变量 | 默认 | 作用 |
| --- | --- | --- |
| `KB_CHUNK_MIN` | 300 | 切片长度下限 |
| `KB_CHUNK_MAX` | 800 | 切片长度上限（整表切片除外） |
| `KB_CHUNK_OVERLAP` | 50 | 同一小节内相邻切片的重叠字数 |
| `KB_CHUNK_TABLE_MAX` | 1500 | 表格整表保留的阈值 |
| `KB_PREFIX_HEADING` | 1 | 向量化文本是否拼上 `heading_path` |

也可以直接传 `ChunkerConfig(...)`：

```python
from kb.chunker import ChunkerConfig, chunk

chunks = chunk(parsed_doc)                                  # 读环境变量
chunks = chunk(parsed_doc, ChunkerConfig(max_len=600))      # 显式覆盖
texts = [c.vector_text() for c in chunks]                   # 带标题前缀
texts = [c.vector_text(prefix_heading=False) for c in chunks]
```

## 7. 测试

```bash
python -m pytest -v
```

四组用例对应四条验收：

| 文件 | 用例数 | 覆盖 |
| --- | --- | --- |
| `tests/test_chunk_sizes.py` | 10 | 800 上限、整表例外、短切片来源小节、不跨标题合并、重叠、配置读取、空文档、id 稳定 |
| `tests/test_heading_path.py` | 9 | 三级路径逐元素相等、兄弟不污染、回到二级、跳级不补空串、三级开头、表格同路径、向量前缀开关 |
| `tests/test_page_range.py` | 7 | 跨页段落 3→4、同页相等、跨三页连续、block 序号、缺页码默认、页眉页脚跳过 |
| `tests/test_table_header.py` | 7 | 每片带表头、行不重不漏、整表保留、阈值上下、拆片长度 |

合计 **4 个测试文件、33 个用例，全部通过**。

## 8. 实测数字

三个虚构样例合计 30 个切片（28 个正文片 + 2 个整表片）：

- 非整表切片最大 **745 字**，全部 `<= 800`；
- 正文切片最小 **306 字**（在来源小节不短于 300 字的切片中）；
- 长度小于 300 的切片共 5 个，其 `source_section_len` 分别为 26、26、26、132、202，全部小于 300；
- 整表切片 2 个（1064 字与 308 字），前者超过 800 且被正确标记为 `is_whole_table`；
- 拆表：40 行数据拆成 3 片，片长 736 / 745 / 641，每片首行均为 `序号 | 类型 | 说明 | 标记`，拼接后与原始 40 行完全一致；
- 跨页段落 `page_from=3`、`page_to=4`；跨三页段落切成 3 片，区间为 3–4、3–5、4–5；
- 同一小节内相邻切片重叠固定 50 字，`overlap_ok` 校验 7/7 组成立。

实测日志（提交在仓库 `logs/` 目录）：

| 文件 | 内容 | 结论行 |
| --- | --- | --- |
| `logs/pytest-3.12.txt` | Python 3.12.10 下 `pytest -v` 全量输出 | `33 passed in 0.08s` |
| `logs/pytest-3.11.txt` | Python 3.11.9 下 `pytest -v` 全量输出 | `33 passed in 0.08s` |
| `logs/chunk_stats.txt` | `scripts/chunk_stats.py` 输出 | 三份样例 16 / 7 / 7 片 |

## 9. 与投标提案的差异

以工单验收原文为准，实现与提案的差别如下：

1. 提案只列了 `KB_CHUNK_MIN` / `KB_CHUNK_MAX` / `KB_CHUNK_OVERLAP`。实现额外提供 `KB_CHUNK_TABLE_MAX` 与 `KB_PREFIX_HEADING` 两个可选开关，默认值与验收一致（1500 / 开），不使用它们时行为不变。
2. 提案描述「硬切推进到最近分句符，仍不行按 800 硬断」。实现保留同一优先级（段落 → 句子 → 等步长硬切），但在三个样例上 `hard_cut` 一次都没触发：所有切点都落在句子或段落边界。
3. 提案写「重叠只在同一小节内相邻切片之间生效」，实现一致：跨小节不重叠，`overlap_prefix_len` 在该小节首片为 0。
4. 提案提到 PDF/Word 解析器不在范围内——实现只接收已解析的 `parsed_doc`，**不包含解析器**，也不做向量化与检索。

## 10. 不在本单范围

PDF/Word/HTML 解析器、向量化与索引、检索与重排、切片落库与鉴权、分词的语义化处理（句子仅按标点规则切）。

## 11. 数据说明

`samples/` 下三个文档与全部测试数据均为虚构内容，不包含任何真实企业名、真实人名或真实业务信息。