"""Tests of the BM25 index and of the chunking of docs/."""

import re
from collections import Counter
from pathlib import Path

import pytest

from office_support.retrieval import (
    DOCS_PATH,
    BM25Index,
    chunk,
    citation,
    stem,
    tokenize,
)

ROOT = DOCS_PATH.parent


@pytest.fixture(scope="module")
def index() -> BM25Index:
    return BM25Index.from_directory()


def _corpus(tmp_path: Path, docs: dict[str, str]) -> BM25Index:
    for name, text in docs.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return BM25Index.from_directory(tmp_path)


# --- Criteria 1 and 2: chunking ------------------------------------------------

def test_one_fragment_per_section():
    fragments = chunk()
    expected = sum(
        len(re.findall(r"^## ", p.read_text(encoding="utf-8"), re.MULTILINE))
        for p in DOCS_PATH.glob("*.md")
    )
    assert len(fragments) == expected
    for f in fragments:
        assert {"doc", "section", "text"} <= set(f)
        assert f["doc"].startswith("docs/") and f["text"]


def test_each_kb_contributes_three_sections():
    per_doc = Counter(f["doc"] for f in chunk() if "/kb-" in f["doc"])
    assert len(per_doc) >= 8
    assert set(per_doc.values()) == {3}


def test_title_distinguishes_equal_sections(index):
    """Among all the "Steps" sections, the one of the VPN document wins."""
    steps = [r for r in index.search("Steps vpn", k=50) if r["section"] == "Steps"]
    assert steps[0]["doc"] == "docs/kb-network-01.md"


# --- Criterion 3: tokenization ---------------------------------------------------

def test_tokenize_without_accents_or_capitals():
    assert tokenize("Expired PASSWORD?") == tokenize("expired password")
    assert tokenize("Expired PASSWORD?") == ["expired", "password"]
    assert tokenize("Café won't") == ["cafe", "wont"]


def test_tokenize_removes_stop_words():
    tokens = tokenize("the email of the office that does not arrive")
    assert not {"the", "of", "that", "does"} & set(tokens)
    assert {"email", "office", "arrive"} <= set(tokens)


@pytest.mark.parametrize("variants", [
    ["restart", "restarts", "restarting", "restarted"],
    ["service", "services"],
    ["degrade", "degraded", "degrades"],
    ["network", "networks"],
    ["printer", "printers"],
])
def test_stem_joins_variants(variants):
    assert len({stem(v) for v in variants}) == 1


def test_stem_does_not_touch_short_words():
    assert stem("vpn") == "vpn"
    assert stem("erp") == "erp"


# --- Criterion 4: BM25 over a small corpus -----------------------------------------

def test_rare_term_weighs_more(tmp_path):
    index = _corpus(tmp_path, {
        "a.md": "# A\n## S\nnetwork network printer",
        "b.md": "# B\n## S\nnetwork network toner",
        "c.md": "# C\n## S\nnetwork network paper",
    })
    # "network" is in all of them; "toner" only in b.md.
    assert index.search("network toner")[0]["doc"] == "docs/b.md"


def test_short_fragment_scores_higher(tmp_path):
    index = _corpus(tmp_path, {
        "short.md": "# X\n## S\nvpn down",
        "long.md": "# X\n## S\nvpn down office device cable monitor keyboard mouse",
    })
    result = index.search("vpn")
    assert [r["doc"] for r in result] == ["docs/short.md", "docs/long.md"]
    assert result[0]["score"] > result[1]["score"]


def test_query_without_matches_returns_empty(index):
    assert index.search("helicopter submarine") == []
    assert index.search("the of and") == []


# --- Criterion 5: quality over the real documents -----------------------------------

@pytest.mark.parametrize("query, expected", [
    ("I have no internet, the vpn is down", "kb-network-01.md"),
    ("faulty network card, cable disconnected", "kb-network-02.md"),
    ("paper jam in the printer", "kb-printer-01.md"),
    ("expired password, locked account", "kb-app_access-02.md"),
    ("mailbox full, I am not receiving emails", "kb-email-02.md"),
    ("response times by priority", "service-catalog.md"),
    ("restart a critical service during business hours", "restart-policy.md"),
    ("restarting critical services", "restart-policy.md"),
    ("my laptop won't turn on", "kb-hardware-01.md"),
    ("my computer is slow", "kb-hardware-03.md"),
    ("no printer is printing", "kb-printer-02.md"),
])
def test_quality_first_result(index, query, expected):
    assert index.search(query)[0]["doc"] == f"docs/{expected}"


def _margin(index: BM25Index, query: str, expected: str) -> float:
    """Score of the expected document / that of the best different document."""
    result = index.search(query, k=50)
    best = next(r["score"] for r in result if r["doc"] == expected)
    other = next(r["score"] for r in result if r["doc"] != expected)
    return best / other


@pytest.mark.parametrize("query", [
    "restart a critical service during business hours",
    "restarting critical services",
])
def test_restart_policy_margin(index, query):
    """kb-printer-02 also talks about restarting; the policy must win comfortably."""
    assert _margin(index, query, "docs/restart-policy.md") >= 1.2


# --- Criterion 6: k, order and determinism --------------------------------------------

@pytest.mark.parametrize("k", [1, 3, 5])
def test_at_most_k_sorted(index, k):
    result = index.search("service down office", k)
    assert 0 < len(result) <= k
    scores = [r["score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_deterministic(index):
    assert index.search("printer not printing", 5) == index.search("printer not printing", 5)
    other = BM25Index.from_directory()
    assert other.search("printer not printing", 5) == index.search("printer not printing", 5)


# --- Criterion 9: citations -------------------------------------------------------------

def test_checkable_citations(index):
    for fragment in index.search("service down restart escalation", 10):
        reference = citation(fragment)
        file, section = reference.split("#")
        assert re.fullmatch(r"docs/[a-z0-9_-]+\.md", file)
        assert (ROOT / file).is_file()
        assert section == fragment["section"]


def test_citation_exact_format():
    assert citation({"doc": "docs/kb-network-01.md", "section": "Steps"}) == \
        "docs/kb-network-01.md#Steps"
