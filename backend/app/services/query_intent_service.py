import re
from typing import Literal

QueryIntent = Literal[
    "capabilities",
    "assistant_info",
    "document_search",
    "fact",
    "summary",
    "comparison",
    "list",
    "calculation",
    "general",
]

_CAPABILITIES_PATTERNS = (
    re.compile(
        r"\b(what|which)\b.*\b(file types?|file formats?|formats?)\b",
        re.I,
    ),
    re.compile(
        r"\b(what|which)\b.*\b(files?|documents?|formats?|extensions?)\b.*"
        r"\b(analy[sz]e|read|support|process|retrieve|extract)\b",
        re.I,
    ),
    re.compile(
        r"\b(supported file types?|supported formats?|file format support|what can you analyze)\b",
        re.I,
    ),
)

_ASSISTANT_INFO_PATTERNS = (
    re.compile(
        r"\b(on|what|which)\b.*\b(basis|method|criteria|process)\b.*"
        r"\b(retriev\w*|search\w*|find\w*|answer\w*|respond\w*)\b",
        re.I,
    ),
    re.compile(
        r"\bhow\b.*\b(do you|does (?:the )?(?:assistant|system|chatbot))\b.*"
        r"\b(retriev\w*|search\w*|find\w*|answer\w*|respond\w*|work\w*)\b",
        re.I,
    ),
    re.compile(
        r"\b(how does this work|how this works|how the system works|"
        r"how the assistant works|how do you work|who are you)\b",
        re.I,
    ),
)

_DOCUMENT_SEARCH_PATTERN = re.compile(
    r"\b(find|search|locate|identify|look\s+for|show\s+me)\b.*"
    r"\b(agreements?|aggreements?|aggrements?|contracts?|mous?|"
    r"memorandums?\s+of\s+understanding|ndas?|non[-\s]?disclosure)\b",
    re.I,
)

_INTENT_PATTERNS: tuple[tuple[QueryIntent, re.Pattern[str]], ...] = (
    (
        "summary",
        re.compile(r"\b(summar(?:y|ize|ise)|overview|key points|highlights)\b", re.I),
    ),
    (
        "comparison",
        re.compile(r"\b(compare|comparison|versus|vs\.?|difference|similarit(?:y|ies))\b", re.I),
    ),
    (
        "calculation",
        re.compile(r"\b(total|sum|average|mean|count|how many|how much|calculate)\b", re.I),
    ),
    (
        "list",
        re.compile(r"\b(list|enumerate|all|every|names of|items)\b", re.I),
    ),
)


def classify_query_intent(query: str) -> QueryIntent:
    """Classify common question shapes without an additional model request."""
    if any(pattern.search(query) for pattern in _CAPABILITIES_PATTERNS):
        return "capabilities"
    if any(pattern.search(query) for pattern in _ASSISTANT_INFO_PATTERNS):
        return "assistant_info"
    if _DOCUMENT_SEARCH_PATTERN.search(query):
        return "document_search"

    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(query):
            return intent

    if re.match(r"^\s*(what|who|when|where|which|how|is|are|does|do|can)\b", query, re.I):
        return "fact"
    return "general"
