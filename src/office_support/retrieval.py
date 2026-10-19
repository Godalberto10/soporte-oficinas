"""Own BM25 index over the sections of the documents in docs/."""

import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

DOCS_PATH = Path(__file__).resolve().parents[2] / "docs"
K1 = 1.5
B = 0.75
STEM_LENGTH = 6
TITLE_WEIGHT = 3  # the document title counts as 3 occurrences

STOP_WORDS = frozenset("""
a about after all also am an and any are as at be been before being both but by
can could did do does doing during each for from had has have having he her here
his how i if in into is it its just me more most my of on once only or our out
own same she should so some such than that the their them then there these they
this those through to too until very was we were what when where which while who
whom why will with would you your
""".split())


def tokenize(text: str) -> list[str]:
    """Lower case, no accents or apostrophes, only letters and digits, no stop words."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("'", "").replace("’", ""))
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", no_accents) if t not in STOP_WORDS]


def stem(word: str) -> str:
    """Approximate stem: no -ing, -ed or plural, no final e, truncated to 6 letters.

    Makes "restart", "restarts", "restarting" and "restarted" (or "service" and
    "services") count as the same term.
    """
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-2]
    elif len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    if len(word) > 4 and word.endswith("e"):
        word = word[:-1]
    return word[:STEM_LENGTH]


def terms(text: str) -> list[str]:
    """Terms that are indexed and searched: stems of the tokens."""
    return [stem(t) for t in tokenize(text)]


def _sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """`# ` title of the document and (`## ` section, content) pairs."""
    title, sections = "", []
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
    return title, [(s, "\n".join(lines).strip()) for s, lines in sections]


def chunk(docs_path: Path = DOCS_PATH) -> list[dict]:
    """One fragment {doc, section, text, title} for each `## ` section."""
    fragments = []
    for path in sorted(Path(docs_path).glob("*.md")):
        title, sections = _sections(path.read_text(encoding="utf-8"))
        for section, text in sections:
            fragments.append({"doc": f"docs/{path.name}", "section": section,
                              "text": text, "title": title})
    return fragments


def citation(fragment: dict) -> str:
    """Verifiable citation of a fragment: docs/<file>.md#<section>."""
    return f"{fragment['doc']}#{fragment['section']}"


def _indexed_text(fragment: dict) -> str:
    """Title (with more weight), section name and content."""
    title = " ".join([fragment.get("title", "")] * TITLE_WEIGHT)
    return f"{title} {fragment['section']} {fragment['text']}"


class BM25Index:
    """BM25 index (k1=1.5, b=0.75) over the stems of the terms of each fragment."""

    def __init__(self, fragments: list[dict]) -> None:
        self.fragments = fragments
        self._frequencies = [Counter(terms(_indexed_text(f))) for f in fragments]
        self._lengths = [sum(c.values()) for c in self._frequencies]
        self._average = sum(self._lengths) / len(fragments) if fragments else 0.0
        self._df = Counter(t for c in self._frequencies for t in c)

    @classmethod
    def from_directory(cls, path: Path = DOCS_PATH) -> "BM25Index":
        """Builds the index with the sections of the .md files of a directory."""
        return cls(chunk(path))

    def _idf(self, term: str) -> float:
        n, df = len(self.fragments), self._df[term]
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _score(self, i: int, wanted: set[str]) -> float:
        frequencies, length = self._frequencies[i], self._lengths[i]
        total = 0.0
        for term in wanted:
            f = frequencies[term]
            if f:
                norm = K1 * (1 - B + B * length / self._average)
                total += self._idf(term) * f * (K1 + 1) / (f + norm)
        return total

    def search(self, query: str, k: int = 3) -> list[dict]:
        """Up to k fragments {doc, section, text, score}, highest first."""
        wanted = set(terms(query))
        scored = [(self._score(i, wanted), f) for i, f in enumerate(self.fragments)]
        positive = [(s, f) for s, f in scored if s > 0]
        positive.sort(key=lambda pair: (-pair[0], pair[1]["doc"], pair[1]["section"]))
        return [{"doc": f["doc"], "section": f["section"], "text": f["text"],
                 "score": round(s, 4)} for s, f in positive[:k]]
