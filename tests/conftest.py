"""pytest 公共夹具：加载 samples 下的虚构样例文档。"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from kb.chunker import ChunkerConfig, chunk  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples")


def load_sample(name: str) -> dict:
    path = os.path.join(SAMPLES, name + ".json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def config() -> ChunkerConfig:
    return ChunkerConfig()


@pytest.fixture(scope="session")
def doc_1() -> dict:
    return load_sample("doc_1")


@pytest.fixture(scope="session")
def doc_2() -> dict:
    return load_sample("doc_2")


@pytest.fixture(scope="session")
def doc_3() -> dict:
    return load_sample("doc_3")


@pytest.fixture(scope="session")
def all_docs(doc_1, doc_2, doc_3):
    return [doc_1, doc_2, doc_3]


@pytest.fixture(scope="session")
def all_chunks(all_docs, config):
    out = []
    for doc in all_docs:
        out.extend(chunk(doc, config))
    return out

