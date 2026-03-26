"""
Deterministic rule-based feature extraction.

Features extracted:
    has_code_block              — fenced code block present
    asks_high_precision         — precision-demanding language
    asks_compare                — comparison request
    asks_reasoning              — explicit reasoning/explanation request
    has_json_like_text          — JSON-like structure present
    num_distinct_requests       — count of distinct tasks/questions
    input_token_count           — approximate token count
"""

import re
from ingestion.models import RuleFeatures

# ---------------------------------------------------------------------------
# Pattern 1: Code blocks
# ---------------------------------------------------------------------------
# Matches triple backticks or triple tildes — standard markdown fenced blocks.
# re.IGNORECASE isn't really needed here but kept for consistency.
_CODE_BLOCK = re.compile(r"```|~~~", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Pattern 2: High precision language
# ---------------------------------------------------------------------------
# Fires when the user demands exactness — signals the model can't paraphrase
# or approximate, it needs to be careful and precise.
#
# exact/exactly         → "give me the exact query"
# precise/precisely     → "be precise about the steps"
# accurate/accurately   → "I need an accurate calculation"
# specific/specifically → "specifically in terms of X"
# correct/correctly     → "the correct way to do this"
# verbatim              → "reproduce this verbatim"
# word-for-word         → "translate word for word"
# no approximation      → "no approximation, exact values"
# must/need to be exact → "the output must be exact"
# without rounding      → "without rounding the result"
# to X decimal places   → "calculate to 4 decimal places"
# ---------------------------------------------------------------------------
_HIGH_PRECISION_TERMS = re.compile(
    r"\b("
    r"exact(?:ly)?|precise(?:ly)?|accurate(?:ly)?|specific(?:ally)?|"
    r"correct(?:ly)?|verbatim|word[- ]for[- ]word|no\s+approximat\w+|"
    r"must\s+be\s+exact|need\s+to\s+be\s+(?:exact|precise|accurate)|"
    r"without\s+rounding|to\s+\d+\s+decimal\s+places"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pattern 3: Comparison language
# ---------------------------------------------------------------------------
# Fires when the user wants two or more things evaluated against each other.
# This is a strong complexity signal — comparisons require the model to
# understand multiple concepts AND produce structured contrast.
#
# compare/comparing/compared  → "compare X and Y"
# contrast                    → "contrast approach A with B"
# difference between          → "difference between SQL and NoSQL"
# versus / vs                 → "Python vs JavaScript"
# which is better/worse/etc   → "which is faster"
# pros and cons               → "pros and cons of microservices"
# trade-off / tradeoff        → "trade-offs between X and Y"
# or (between two nouns)      → "should I use Redis or Postgres"
#   ↑ this is the new one — catches natural "or" comparisons that
#     don't use explicit comparison vocabulary
# better than / worse than    → "is X better than Y"
# advantage/disadvantage      → "advantages of using Docker"
# ---------------------------------------------------------------------------
_COMPARE_TERMS = re.compile(
    r"\b("
    r"compar[ei]\w*|contrast\w*|difference[s]?\s+between|versus|vs\.?|"
    r"which\s+is\s+(better|worse|faster|cheaper|more|less|preferred|recommended)|"
    r"pros?\s+and\s+cons?|trade[- ]?off\w*|"
    r"(better|worse|faster|slower|cheaper|more\s+efficient)\s+than|"
    r"advantage[s]?\s+of|disadvantage[s]?\s+of|"
    r"should\s+I\s+use\s+\w+\s+or\s+\w+|"   # "should I use X or Y"
    r"when\s+(?:should|would|do)\s+(?:I|you|we)\s+use|"  # "when should I use X"
    r"(?:choose|pick|select|prefer)\s+between"            # "choose between X and Y"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pattern 4: Reasoning / explanation language
# ---------------------------------------------------------------------------
# Fires when the user wants understanding, not just an answer.
# This means the model needs to construct an explanation, not just retrieve a fact.
#
# explain / explanation       → "explain how X works"
# reason / reasoning          → "what is the reasoning behind"
# why does / why is           → "why does this fail"
# how does / how is           → "how does backprop work"
# how do I / how can I        → "how do I fix this"
# step-by-step                → "step by step guide"
# walk me through             → "walk me through the process"
# break it down               → "break down this concept"
# think through               → "think through the implications"
# justify                     → "justify this architectural choice"
# elaborate                   → "can you elaborate on X"
# describe the process        → "describe the process of X"
# what causes                 → "what causes memory leaks" — new
# how does X lead to Y        → "how does this lead to that" — new
# help me understand          → "help me understand transformers" — new
# ---------------------------------------------------------------------------
_REASONING_TERMS = re.compile(
    r"\b("
    r"explain\w*|reason\w*|why\s+does|why\s+is|why\s+do|why\s+are|"
    r"how\s+does|how\s+is|how\s+do\s+(?:I|you|we)|how\s+can\s+(?:I|you|we)|"
    r"step[- ]by[- ]step|walk\s+me\s+through|break\s+(?:it\s+)?down|"
    r"think\s+through|justify|elaborate|describe\s+the\s+process|"
    r"what\s+causes|what\s+makes|help\s+me\s+understand|"
    r"underlying\s+(?:reason|mechanism|concept|principle)|"
    r"intuition\s+(?:behind|for)|in\s+depth|deep\s+dive"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pattern 5: JSON-like text
# ---------------------------------------------------------------------------
# Matches { ... } or [ ... ] with at least 3 chars inside.
# Signals the query contains structured data the model needs to process.
# The [^]{}\n] part means: any char that is NOT a brace or newline,
# so it avoids matching across multiple lines or nested structures incorrectly.
_JSON_LIKE = re.compile(r"[\[{][^]{}\n]{3,}[}\]]")


# ---------------------------------------------------------------------------
# Pattern 6: Distinct request counter
# ---------------------------------------------------------------------------
# Counts how many separate tasks/questions are in a single query.
# Each match = one additional request boundary detected.
#
# Groups covered:
#
# A) Question marks
#    "what is X? how do I Y? why does Z?"  → 3 matches
#
# B) Classic connector words
#    "also", "additionally", "furthermore"
#    "also tell me...", "and also explain..."
#
# C) Imperative verbs after "and" or standalone
#    "...and write me the code"
#    "...and also create a test"
#
# D) Comma-separated imperatives  ← NEW
#    "summarize this, find the themes, suggest improvements"
#    matches ", find" / ", suggest" / ", list" etc.
#    Pattern: comma + optional space + imperative verb
#
# E) "then" as a sequencing word  ← NEW
#    "do X, then do Y, then do Z"
#    signals chained sequential tasks
#
# F) "and how" / "and what" / "and why"  ← NEW
#    "explain what is wrong and how to fix it"
#    "describe the issue and what caused it"
#
# G) "as well as" / "in addition to"  ← NEW
#    "fix the bug as well as add tests"
# ---------------------------------------------------------------------------
_REQUEST_SPLITTERS = re.compile(
    r"("
    # A) question marks
    r"\?|"
    # B) standalone connector words
    r"\b(also|additionally|furthermore)\b|"
    # C) "and [also] [please] <imperative verb>"
    r"\band\s+(?:also\s+)?(?:please\s+)?"
    r"(?:tell|show|give|list|explain|describe|calculate|write|create|"
    r"build|summarize|compare|find|check|verify|help|generate|implement|"
    r"provide|return|output|print|display|suggest|recommend|identify|"
    r"analyse|analyze|evaluate|review|test|fix|update|refactor)\b|"
    # D) comma + imperative verb (catches "summarize X, find Y, suggest Z")
    r",\s*(?:then\s+)?"
    r"(?:tell|show|give|list|explain|describe|calculate|write|create|"
    r"build|summarize|compare|find|check|verify|help|generate|implement|"
    r"provide|return|output|print|display|suggest|recommend|identify|"
    r"analyse|analyze|evaluate|review|test|fix|update|refactor)\b|"
    # E) "then" as a task sequencer
    r"\bthen\s+"
    r"(?:tell|show|give|list|explain|describe|calculate|write|create|"
    r"build|summarize|compare|find|check|verify|help|generate|implement|"
    r"provide|return|output|print|display|suggest|recommend|identify|"
    r"analyse|analyze|evaluate|review|test|fix|update|refactor)\b|"
    # F) "and how/what/why/where/when" — implies a follow-up question
    r"\band\s+(?:how|what|why|where|when)\s+|"
    # G) "as well as" / "in addition to" / "along with"
    r"\b(?:as\s+well\s+as|in\s+addition\s+to|along\s+with)\b"
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pattern 7: Token splitter
# ---------------------------------------------------------------------------
# Offline token count estimator. No API needed.
# \w+       → matches whole words (letters, digits, underscores)
# [^\w\s]   → matches individual punctuation/special characters
# Together they approximate the way real tokenizers split text.
# Not perfectly accurate but good enough for routing thresholds.
_TOKEN_SPLIT = re.compile(r"\w+|[^\w\s]")

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class RuleExtractor:
    """
    Stateless extractor.  Call extract(query) → RuleFeatures.
    Thread-safe (no mutable state).
    """

    def extract(self, query: str) -> RuleFeatures:
        """
        Extract all rule-based features from a raw query string.

        Args:
            query: The raw user query text.

        Returns:
            RuleFeatures with all 7 fields populated.
        """
        if not query or not query.strip():
            return self._empty()

        return RuleFeatures(
            has_code_block=self._has_code_block(query),
            asks_high_precision=self._asks_high_precision(query),
            asks_compare=self._asks_compare(query),
            asks_reasoning=self._asks_reasoning(query),
            has_json_like_text=self._has_json_like_text(query),
            num_distinct_requests=self._count_distinct_requests(query),
            input_token_count=self._count_tokens(query),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_code_block(text: str) -> bool:
        return bool(_CODE_BLOCK.search(text))

    @staticmethod
    def _asks_high_precision(text: str) -> bool:
        return bool(_HIGH_PRECISION_TERMS.search(text))

    @staticmethod
    def _asks_compare(text: str) -> bool:
        return bool(_COMPARE_TERMS.search(text))

    @staticmethod
    def _asks_reasoning(text: str) -> bool:
        return bool(_REASONING_TERMS.search(text))

    @staticmethod
    def _has_json_like_text(text: str) -> bool:
        return bool(_JSON_LIKE.search(text))

    @staticmethod
    def _count_distinct_requests(text: str) -> int:
        """
        Heuristic: count splits caused by '?' or imperative connector words.
        Minimum is 1 (the query itself).
        """
        splits = _REQUEST_SPLITTERS.findall(text)
        return max(1, len(splits))

    @staticmethod
    def _count_tokens(text: str) -> int:
        return len(_TOKEN_SPLIT.findall(text))

    @staticmethod
    def _empty() -> RuleFeatures:
        return RuleFeatures(
            has_code_block=False,
            asks_high_precision=False,
            asks_compare=False,
            asks_reasoning=False,
            has_json_like_text=False,
            num_distinct_requests=1,
            input_token_count=0,
        )