"""Keyword search baseline (BM25).

This is the "before" picture: how a typical store search works today. It
matches the words in the query against the words in each product's title,
category and description. It knows nothing about meaning, so "a tool to
separate egg whites" only finds products that share those exact words.

BM25 is the standard keyword-ranking formula used by most search engines
(e.g. Elasticsearch). It is written here in plain Python, with no extra
libraries, so it is easy to read and explain.

  score(query, product) = sum over query words w of
        IDF(w) * tf(w) * (k1 + 1) / (tf(w) + k1 * (1 - b + b * len / avg_len))

  - tf(w):  how often w appears in the product text
  - IDF(w): rarer words count more (e.g. "egg" outweighs "steel")
  - k1, b:  standard settings that dampen repeated words and long texts
"""

import math
import re
from collections import Counter

STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "to", "of", "in", "on", "with", "my", "me",
    "i", "is", "it", "that", "this", "something", "some", "need", "want", "looking",
    "can", "you", "your", "from", "at", "by", "be", "will", "which", "what", "thing",
    "x", "cm", "in.", "set", "pieces", "piece",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lower-case, split into words, drop filler words, crude plural -> singular."""
    out = []
    for t in TOKEN_RE.findall(text.lower()):
        if t in STOPWORDS:
            continue
        if len(t) > 4 and t.endswith("sses"):
            t = t[:-2]                                  # glasses -> glass
        elif len(t) > 3 and t.endswith("es") and not t.endswith("ses"):
            t = t[:-2] if t[-3] in "hsx" else t[:-1]   # boxes -> box, knives stays 'knive'
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]                                  # separators -> separator
        out.append(t)
    return out


class BM25Index:
    def __init__(self, docs: dict[str, str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.ids = list(docs)
        self.tf = {i: Counter(tokenize(docs[i])) for i in self.ids}
        self.len = {i: sum(self.tf[i].values()) for i in self.ids}
        self.avg_len = sum(self.len.values()) / max(len(self.ids), 1)
        df = Counter(w for i in self.ids for w in self.tf[i])
        n = len(self.ids)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        """Return up to k (product_id, score) pairs, best first. Score 0 = no word matched."""
        q = tokenize(query)
        scores = []
        for i in self.ids:
            tf, s = self.tf[i], 0.0
            for w in q:
                f = tf.get(w, 0)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg_len))
            if s > 0:
                scores.append((i, s))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]
