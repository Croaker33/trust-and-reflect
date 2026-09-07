"""
Risk-flag keyword lists and flag conditions of the Confidence Analyzer's
rule layer.

Paper: "Trust and Reflect: Process Critique and Confidence Auditing for
Web Search Agents" (NLPIR 2026), Sect. 3.4 -- the *evidence consistency*
and *answer specificity* sub-scores, the risk-aware caps, and the
retry-critical flag conditions. The two supplementary case studies show
the resulting rule report on a concrete question, including which flag
fired and which cap bound.

Two keyword lexicons are used:

  CONFLICT_WORDS   scanned over the evidence text and over the critic's
                   own critique / progress fields; each independent hit
                   lowers evidence consistency.
  UNCERTAIN_WORDS  scanned over the final answer only; a hit both raises
                   ANSWER_CONTAINS_UNCERTAINTY and withholds part of the
                   answer-specificity score.

Both are curated for the Chinese-language answers of Web24 and are an
implementation detail, not part of the method. Sect. 5 names their
semi-automatic maintenance as future work.
"""

import re
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------
# Lexicons
# --------------------------------------------------------------------------
# Case-insensitive substring test over the concatenated evidence text, and
# a case-sensitive substring test over the critic's text fields.
CONFLICT_WORDS = (
    "冲突",
    "矛盾",
    "不一致",
    "不同说法",
    "相互矛盾",
    "conflict",
    "inconsistent",
)

# Substring test over the final answer.
UNCERTAIN_WORDS = (
    "无法确定",
    "不确定",
    "没有找到",
    "未找到",
    "可能",
    "大概",
    "似乎",
    "无法确认",
)

# --------------------------------------------------------------------------
# Risk flags
# --------------------------------------------------------------------------
# Emitted by the rule layer. CRITIC_LATEST_<STATE> is generated
# dynamically from the critic's most recent state whenever that state is
# anything other than SUFFICIENT, so CRITIC_LATEST_CONFLICTING and
# CRITIC_LATEST_OFF_TRACK below are the two instances that are also
# retry-critical.
RISK_FLAG_CONDITIONS = {
    "NO_EXTRACTED_SOURCE": "no evidence item with a parseable URL was recovered from the history",
    "SINGLE_DOMAIN_EVIDENCE": "at least one source, but all sources share one domain",
    "LOW_EVIDENCE_COVERAGE": "evidence_coverage < 0.45",
    "LOW_SOURCE_RELIABILITY": "source_reliability < 0.45",
    "POSSIBLE_CONFLICT": "evidence_consistency < 0.55",
    "ANSWER_CONTAINS_UNCERTAINTY": "the final answer contains an UNCERTAIN_WORDS hit",
    "CRITIC_LATEST_<STATE>": "the critic's latest state is not SUFFICIENT",
}

# A single member of this set forces a retry regardless of the fused score.
CRITICAL_RETRY_RISKS = {
    "NO_EXTRACTED_SOURCE",
    "POSSIBLE_CONFLICT",
    "CRITIC_LATEST_CONFLICTING",
    "CRITIC_LATEST_OFF_TRACK",
}

# Critic states that count as a consistency failure when read from the
# state history by the evidence-consistency sub-score.
CRITIC_CONFLICT_STATES = {"CONFLICTING", "OFF_TRACK"}
CRITIC_OK_STATE = "SUFFICIENT"

# --------------------------------------------------------------------------
# Flag thresholds
# --------------------------------------------------------------------------
EVIDENCE_COVERAGE_FLAG_THRESHOLD = 0.45
SOURCE_RELIABILITY_FLAG_THRESHOLD = 0.45
EVIDENCE_CONSISTENCY_FLAG_THRESHOLD = 0.55

# Independent of LOW_EVIDENCE_COVERAGE: a severe coverage gap is a
# coverage flag *and* answer-keyword support below this value, and forces
# a retry the same way a critical flag does.
SEVERE_COVERAGE_GAP_ANSWER_SUPPORT = 0.35

# --------------------------------------------------------------------------
# Risk-aware caps
# --------------------------------------------------------------------------
# Applied as `min(score, *applicable_caps)`. The LLM layer cannot raise a
# score past a cap that fired; caps are applied twice, once inside the
# rule layer and once after rule/LLM fusion.
RULE_LAYER_CAPS = {
    "no_extracted_source": 0.42,       # source_count == 0
    "possible_conflict": 0.58,         # POSSIBLE_CONFLICT flag
    "very_low_coverage": 0.55,         # evidence_coverage < 0.35
    "critic_latest_not_sufficient": 0.65,
}

MERGED_CAPS = {
    "NO_EXTRACTED_SOURCE": 0.45,
    "LOW_EVIDENCE_COVERAGE": 0.62,
    "POSSIBLE_CONFLICT": 0.60,
    "CRITIC_LATEST_*": 0.68,
}

# --------------------------------------------------------------------------
# Sub-score fusion and decision thresholds
# --------------------------------------------------------------------------
# Rule-layer sub-score weights (sum to 1.0).
RULE_SUBSCORE_WEIGHTS = {
    "evidence_coverage": 0.35,
    "source_reliability": 0.25,
    "evidence_consistency": 0.25,
    "answer_specificity": 0.15,
}

# Fixed convex combination of the two layers.
RULE_WEIGHT = 0.40
LLM_WEIGHT = 0.60

# Reporting threshold; retry threshold. A retry also fires on any
# critical flag or on a severe coverage gap, independent of the score.
CONFIDENCE_THRESHOLD = 0.75
CONFIDENCE_RETRY_THRESHOLD = 0.60

# Score -> reported band.
CONFIDENCE_LEVEL_BOUNDS = {"HIGH": 0.80, "MEDIUM": 0.50}


def contains_uncertainty(text: str) -> bool:
    """True if the final answer hits UNCERTAIN_WORDS."""
    return any(word in str(text) for word in UNCERTAIN_WORDS)


def score_evidence_consistency(
    evidence_text: str,
    critic_evaluations: List[Dict],
) -> Tuple[float, List[str]]:
    """
    The *evidence consistency* sub-score in [0, 1], plus the reasons found.

    Starts at 0.85 with no signal and loses 0.20 per independent conflict
    reason, floored at 0.25. Reasons come from three places: a
    CONFLICT_WORDS hit in the evidence text, a critic state in
    CRITIC_CONFLICT_STATES, and a CONFLICT_WORDS hit inside the critic's
    own critique or progress text.
    """
    reasons: List[str] = []
    lowered = str(evidence_text).lower()

    conflict_hits = [word for word in CONFLICT_WORDS if word.lower() in lowered]
    if conflict_hits:
        reasons.append(f"证据文本包含冲突信号: {', '.join(conflict_hits[:3])}")

    for evaluation in critic_evaluations:
        state = str(evaluation.get("state", "")).upper()
        suggestion = str(evaluation.get("critique_and_suggestion", ""))
        assessment = str(evaluation.get("progress_assessment", ""))
        if state in CRITIC_CONFLICT_STATES:
            reasons.append(f"critic 状态为 {state}")
        if any(word in suggestion + assessment for word in CONFLICT_WORDS):
            reasons.append("critic 提到信息冲突或不一致")

    if not reasons:
        return 0.85, []
    return max(0.25, 0.85 - 0.20 * len(reasons)), reasons[:3]


def score_answer_specificity(final_answer: str) -> float:
    """
    The *answer specificity* sub-score in [0, 1].

    An empty answer scores 0.0. Otherwise a 0.45 base plus four additive
    bonuses: length at least 40 characters (+0.20), contains a digit
    (+0.12), contains a word-like or CJK token (+0.12), and free of
    UNCERTAIN_WORDS (+0.11).
    """
    answer = str(final_answer).strip()
    if not answer:
        return 0.0
    score = 0.45
    if len(answer) >= 40:
        score += 0.20
    if re.search(r"\d", answer):
        score += 0.12
    if re.search(r"[A-Za-z][A-Za-z0-9_.+-]{1,}|[一-鿿]{2,}", answer):
        score += 0.12
    if not contains_uncertainty(answer):
        score += 0.11
    return max(0.0, min(1.0, score))


def is_critical_retry_risk(risk_flag: str) -> bool:
    """True if this one flag is enough to force a retry."""
    return risk_flag in CRITICAL_RETRY_RISKS
