from __future__ import annotations

from collections import Counter
from math import log
import re


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
TOKEN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+|[a-z0-9_]+")


def bm25_scores(
    documents: list[tuple[str, str]],
    queries: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> dict[str, float]:
    """Return normalized BM25 scores keyed by document id."""
    if not documents:
        return {}

    tokenized_documents = [_tokenize(text) for _, text in documents]
    document_lengths = [len(tokens) for tokens in tokenized_documents]
    average_length = sum(document_lengths) / len(document_lengths) if document_lengths else 0.0
    if average_length <= 0:
        return {document_id: 0.0 for document_id, _ in documents}

    frequencies = [Counter(tokens) for tokens in tokenized_documents]
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_documents:
        document_frequency.update(set(tokens))

    raw_scores = [0.0 for _ in documents]
    for query in queries:
        query_tokens = _tokenize(query)
        if not query_tokens:
            continue
        for token in set(query_tokens):
            idf = log(1 + (len(documents) - document_frequency[token] + 0.5) / (document_frequency[token] + 0.5))
            for index, token_frequency in enumerate(frequencies):
                frequency = token_frequency[token]
                if frequency <= 0:
                    continue
                denominator = frequency + k1 * (
                    1 - b + b * document_lengths[index] / average_length
                )
                raw_scores[index] += idf * (frequency * (k1 + 1)) / denominator

    max_score = max(raw_scores, default=0.0)
    if max_score <= 0:
        return {document_id: 0.0 for document_id, _ in documents}
    return {
        document_id: raw_scores[index] / max_score
        for index, (document_id, _) in enumerate(documents)
    }


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for match in TOKEN_RE.findall(text.lower()):
        if CJK_RE.fullmatch(match):
            tokens.extend(match)
            tokens.extend(match[index : index + 2] for index in range(len(match) - 1))
        else:
            tokens.append(match)
    return tokens
