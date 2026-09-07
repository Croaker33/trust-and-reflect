"""
Domain-authority rules of the Confidence Analyzer's rule layer.

Paper: "Trust and Reflect: Process Critique and Confidence Auditing for
Web Search Agents" (NLPIR 2026), Sect. 3.4 -- the *source reliability*
sub-score.

Every retrieved evidence item is classified into exactly one of four
tiers by `classify_source(domain, title)`, and the tier is mapped to a
numeric reliability by `SOURCE_QUALITY_SCORE`. The classifier is
deliberately ordered: the weak-source test runs first, so a forum thread
hosted under an otherwise authoritative domain is still treated as weak.

The lists are curated for the Chinese-language web of the Web24
collection window and are an implementation detail, not part of the
method: replacing them changes the rule layer's inputs but not the
architecture. Sect. 5 names their semi-automatic maintenance as future
work.
"""

from urllib.parse import urlparse
from typing import List, Optional

# --------------------------------------------------------------------------
# Tier 1 -- authoritative by top-level / second-level domain suffix
# --------------------------------------------------------------------------
# Matched with `domain.endswith(suffix)`, i.e. on the registrable domain
# after the leading "www." is stripped.
HIGH_AUTHORITY_SUFFIXES = (
    ".gov",
    ".gov.cn",
    ".edu",
    ".edu.cn",
    ".ac.cn",
    ".org",
)

# --------------------------------------------------------------------------
# Tier 1 -- authoritative by substring of "<domain> <title>"
# --------------------------------------------------------------------------
# Case-insensitive substring test. Covers named institutional publishers
# that carry no authoritative suffix, plus Chinese-language markers that
# appear in the page title rather than the host name.
HIGH_AUTHORITY_KEYWORDS = (
    "official",
    "gov",
    "edu",
    "who.int",
    "worldbank.org",
    "imf.org",
    "oecd.org",
    "un.org",
    "stats.gov.cn",
    "people.com.cn",
    "xinhuanet.com",
    "央视",
    "新华社",
    "官网",
    "官方",
    "政府",
    "大学",
    "研究院",
)

# --------------------------------------------------------------------------
# Tier 3 -- weak sources (user-generated, aggregator, self-publishing)
# --------------------------------------------------------------------------
# Tested before the two authoritative lists, so this list wins on
# conflict. Case-insensitive substring test over "<domain> <title>".
WEAK_SOURCE_KEYWORDS = (
    "zhihu",
    "baidu",
    "blog",
    "bbs",
    "forum",
    "csdn",
    "tieba",
    "weibo",
    "reddit",
    "quora",
    "medium.com",
    "toutiao",
    "搜狐",
    "网易号",
    "百家号",
)

# --------------------------------------------------------------------------
# Tier -> reliability
# --------------------------------------------------------------------------
# "medium" is any resolvable domain matching neither list; "unknown" is an
# evidence item whose URL failed to parse. An unknown source is scored
# above a weak one on purpose: absence of a host name is less informative
# than a positive weak-source match.
SOURCE_QUALITY_SCORE = {
    "high": 0.92,
    "medium": 0.68,
    "low": 0.35,
    "unknown": 0.50,
}

# Diversity bonus added to the mean item reliability: 0.04 per distinct
# domain, saturating at three domains (max +0.12). The result is clamped
# to [0, 1].
DOMAIN_DIVERSITY_BONUS_PER_DOMAIN = 0.04
DOMAIN_DIVERSITY_BONUS_MAX_DOMAINS = 3


def normalize_domain(url: str) -> str:
    """Registrable host of `url`, lower-cased, with a leading "www." removed."""
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return domain[4:] if domain.startswith("www.") else domain


def classify_source(domain: str, title: str = "") -> str:
    """Return one of "low", "high", "medium", "unknown" for one evidence item."""
    source_text = f"{domain} {title}".lower()
    if any(keyword.lower() in source_text for keyword in WEAK_SOURCE_KEYWORDS):
        return "low"
    if any(domain.endswith(suffix) for suffix in HIGH_AUTHORITY_SUFFIXES):
        return "high"
    if any(keyword.lower() in source_text for keyword in HIGH_AUTHORITY_KEYWORDS):
        return "high"
    if domain:
        return "medium"
    return "unknown"


def score_source_reliability(evidence_items: List[dict]) -> float:
    """
    The *source reliability* sub-score in [0, 1].

    `evidence_items` are dicts carrying at least "domain" and
    "source_quality" (as produced by `classify_source`). An empty evidence
    set scores 0.0, which is what triggers the NO_EXTRACTED_SOURCE flag and
    the 0.42 cap in `risk_flags.py`.
    """
    if not evidence_items:
        return 0.0
    scores = [
        SOURCE_QUALITY_SCORE.get(item.get("source_quality", "unknown"), 0.50)
        for item in evidence_items
    ]
    distinct_domains = {item.get("domain") for item in evidence_items if item.get("domain")}
    diversity_bonus = (
        min(len(distinct_domains), DOMAIN_DIVERSITY_BONUS_MAX_DOMAINS)
        * DOMAIN_DIVERSITY_BONUS_PER_DOMAIN
    )
    return max(0.0, min(1.0, sum(scores) / len(scores) + diversity_bonus))
