"""切片统计：输出切片数、长度分布、重叠率、表格片数。

用法：python scripts/chunk_stats.py [samples/doc_1.json ...]
不指定文件时统计 samples 目录下全部样例。
"""

from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from kb.chunker import ChunkerConfig, chunk  # noqa: E402


def overlap_ok(left: str, right: str, size: int) -> bool:
    """校验后一片开头正好是前一片结尾的 size 个字。"""
    if size <= 0:
        return True
    if len(left) < size or len(right) < size:
        return False
    return left[-size:] == right[:size]


def stats_for(path: str, config: ChunkerConfig) -> dict:
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    chunks = chunk(doc, config)

    sizes = sorted(len(c.text) for c in chunks)
    prose = [c for c in chunks if not c.is_whole_table]
    pairs = []
    for left, right in zip(chunks, chunks[1:]):
        if left.section_index != right.section_index or left.is_table or right.is_table:
            continue
        pairs.append((left, right))
    overlaps = [config.overlap for _ in pairs]
    verified = sum(1 for left, right in pairs if overlap_ok(left.text, right.text, config.overlap))
    ratios = [config.overlap / float(len(right.text)) for _, right in pairs if right.text]

    buckets = {"<300": 0, "300-499": 0, "500-799": 0, "800-1499": 0, ">=1500": 0}
    for size in sizes:
        if size < 300:
            buckets["<300"] += 1
        elif size < 500:
            buckets["300-499"] += 1
        elif size < 800:
            buckets["500-799"] += 1
        elif size < 1500:
            buckets["800-1499"] += 1
        else:
            buckets[">=1500"] += 1

    return {
        "file": os.path.basename(path),
        "blocks": len(doc.get("blocks", [])),
        "chunks": len(chunks),
        "min_len": min(sizes) if sizes else 0,
        "max_len": max(sizes) if sizes else 0,
        "mean_len": (sum(sizes) / float(len(sizes))) if sizes else 0.0,
        "median_len": (sizes[len(sizes) // 2] if sizes else 0),
        "buckets": buckets,
        "whole_table_chunks": sum(1 for c in chunks if c.is_whole_table),
        "table_piece_chunks": sum(1 for c in chunks if c.is_table_piece),
        "table_chunks": sum(1 for c in chunks if c.is_table),
        "short_chunks": sum(1 for c in chunks if len(c.text) < config.min_len),
        "over_max": sum(1 for c in prose if len(c.text) > config.max_len),
        "overlap_pairs": len(pairs),
        "overlap_verified": verified,
        "overlap_ratio_mean": (sum(ratios) / float(len(ratios))) if ratios else 0.0,
        "overlap_expected": config.overlap,
    }


def render(rows, config: ChunkerConfig) -> str:
    lines = []
    lines.append("chunk stats (KB_CHUNK_MIN=%d, KB_CHUNK_MAX=%d, KB_CHUNK_OVERLAP=%d, KB_CHUNK_TABLE_MAX=%d)"
                 % (config.min_len, config.max_len, config.overlap, config.table_max))
    lines.append("")
    head = "%-12s %6s %7s %7s %7s %8s %7s %8s %9s" % (
        "file", "blocks", "chunks", "min", "max", "mean", "median", "short", "over_max")
    lines.append(head)
    lines.append("-" * len(head))
    for row in rows:
        lines.append("%-12s %6d %7d %7d %7d %8.1f %7d %8d %9d" % (
            row["file"], row["blocks"], row["chunks"], row["min_len"], row["max_len"],
            row["mean_len"], row["median_len"], row["short_chunks"], row["over_max"]))
    lines.append("")
    lines.append("length buckets:")
    order = ["<300", "300-499", "500-799", "800-1499", ">=1500"]
    lines.append("  %-10s %s" % ("bucket", " ".join("%-10s" % row["file"] for row in rows)))
    for name in order:
        lines.append("  %-10s %s" % (name, " ".join("%-10d" % row["buckets"][name] for row in rows)))
    lines.append("")
    lines.append("tables & overlap:")
    lines.append("  %-12s %s" % ("file", " ".join("%-10s" % row["file"] for row in rows)))
    for key, label in (
        ("table_chunks", "table_chunks"),
        ("whole_table_chunks", "whole_table"),
        ("table_piece_chunks", "table_pieces"),
        ("overlap_pairs", "overlap_pairs"),
        ("overlap_verified", "overlap_ok"),
    ):
        lines.append("  %-12s %s" % (label, " ".join("%-10d" % row[key] for row in rows)))
    lines.append("  %-12s %s" % ("overlap_ratio", " ".join("%-10.3f" % row["overlap_ratio_mean"] for row in rows)))
    lines.append("")
    lines.append("overlap 说明：同一小节内相邻切片固定重叠 %d 字（overlap_ratio = %d / 后一片长度）。"
                 % (config.overlap, config.overlap))
    lines.append("overlap_ok 计数校验 left[-%d:] == right[:%d] 成立的相邻片对数。" % (config.overlap, config.overlap))
    return "\n".join(lines)


def main(argv) -> int:
    config = ChunkerConfig.from_env()
    paths = argv[1:] or sorted(glob.glob(os.path.join(ROOT, "samples", "doc_*.json")))
    if not paths:
        print("no sample documents found")
        return 1
    rows = [stats_for(path, config) for path in paths]
    print(render(rows, config))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
