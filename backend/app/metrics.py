"""Creativity / agency metrics - HLD 6.1 Module 4 and eval 10.2.

Human Agency Retention Rate is the headline number the interface shows live.
Defined as the share of the student's draft that is NOT lexically traceable to
anything the AI put on screen.
"""
import re

_WORD = re.compile(r"[a-z0-9']+")
NGRAM = 5


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _ngrams(tokens: list[str], n: int = NGRAM) -> set[tuple]:
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def levenshtein(a: str, b: str) -> int:
    """Classic edit distance, iterative and memory-light."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _lcs_length(a: list[str], b: list[str]) -> int:
    """Longest common subsequence length, row-rolled to stay O(min(n,m)) memory."""
    if not a or not b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = [0] * (len(b) + 1)
    for token in a:
        cur = [0]
        for j, other in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if token == other else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def rouge_l_recall(candidate: str, reference: str) -> float:
    """ROUGE-L recall of `candidate` against `reference`.

    Chakrabarty et al. (C&C '24, Figure 7) measure a model's contribution to a
    finished story as the fraction of model-written text still recoverable from
    the final draft, via ROUGE-L recall. Reporting the same statistic makes our
    numbers directly comparable to that published baseline.

    Here: how much of what the AI said survives inside the student's draft.
    """
    cand = _tokens(candidate)
    ref = _tokens(reference)
    if not cand:
        return 0.0
    return round(_lcs_length(cand, ref) / len(cand), 4)


def agency_report(draft: str, ai_texts: list[str]) -> dict:
    """How much of this draft is the student's own language?

    Returns a ratio in [0,1] plus the raw counts, so a researcher reading the
    export can reconstruct the number rather than trusting it.
    """
    draft_tokens = _tokens(draft)
    total_words = len(draft_tokens)
    if total_words == 0:
        return {
            "agency_ratio": 1.0, "total_words": 0, "borrowed_ngrams": 0,
            "total_ngrams": 0, "closest_edit_distance": None,
            "ai_retention_rouge_l": 0.0,
        }

    draft_grams = _ngrams(draft_tokens)
    ai_grams: set[tuple] = set()
    for t in ai_texts:
        ai_grams |= _ngrams(_tokens(t))

    borrowed = len(draft_grams & ai_grams)
    total = max(len(draft_grams), 1)
    ratio = 1.0 - (borrowed / total)

    # HLD 10.2 names Levenshtein explicitly: distance to the nearest AI turn.
    closest = None
    if ai_texts:
        closest = min(levenshtein(draft[:600], t[:600]) for t in ai_texts)

    # Paper-comparable view: of everything the AI put on screen, how much of it
    # ended up inside the student's draft?
    joined_ai = " ".join(ai_texts)
    retention = rouge_l_recall(joined_ai, draft) if joined_ai.strip() else 0.0

    return {
        "agency_ratio": round(max(0.0, min(1.0, ratio)), 4),
        "total_words": total_words,
        "borrowed_ngrams": borrowed,
        "total_ngrams": total,
        "closest_edit_distance": closest,
        "ai_retention_rouge_l": retention,
    }
