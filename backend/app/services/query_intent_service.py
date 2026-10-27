import os
import re
from typing import Any, Dict, List, Literal

QueryIntent = Literal[
    "capabilities",
    "assistant_info",
    "direct_answer",
    "media",
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

_DOCUMENT_REQUEST_PATTERN = re.compile(
    r"\b(?:summari[sz]e|compare|search|find|locate|identify|extract|list|"
    r"review|analy[sz]e|read|scan)\b.{0,60}\b(?:drive|files?|documents?|"
    r"pdfs?|spreadsheets?|reports?|contracts?|agreements?|invoices?|"
    r"receipts?|policies|records?|meeting notes?)\b|"
    r"\b(?:drive|files?|documents?|pdfs?|spreadsheets?|reports?|contracts?|"
    r"agreements?|invoices?|receipts?|policies|records?|meeting notes?)\b"
    r".{0,50}\b(?:say|contain|mention|show|include|state|summari[sz]e|"
    r"compare|find|search|extract|list|analy[sz]e|read|review)\b|"
    r"\b(?:in|from|inside|within|across|among|according to|based on)\b"
    r".{0,40}\b(?:my|our|the|these|those|selected|connected)?\s*"
    r"(?:google\s+)?(?:drive|files?|documents?|pdfs?|spreadsheets?|"
    r"reports?|contracts?|agreements?|invoices?|receipts?|policies|"
    r"records?|meeting notes?)\b|"
    r"\b(?:my|our)\s+(?:google\s+)?(?:drive|files?|documents?|reports?|"
    r"contracts?|agreements?|invoices?|receipts?|policies|records?|"
    r"meeting notes?)\b",
    re.I,
)
_PERSONAL_CONTEXT_PATTERN = re.compile(
    r"\b(?:my|our|company(?:'s)?|organization(?:'s)?|team(?:'s)?|"
    r"project(?:'s)?)\b.{0,40}\b(?:status|progress|plan|budget|deadline|"
    r"priorities|deliverables|timeline|milestones)\b",
    re.I,
)
_BUSINESS_DATA_PATTERN = re.compile(
    r"\b(?:revenue|sales figures?|expenses?|payroll|salaries|budgets?|"
    r"employees?|deadlines?|deliverables|transactions|payments|"
    r"account balances?)\b",
    re.I,
)
_TOPIC_RELATION_PATTERN = re.compile(
    r"\bhow\b.{1,80}\b(?:affect\w*|effect\w*|impact\w*|influenc\w*|"
    r"chang\w*|increase\w*|decreas\w*)\b",
    re.I,
)
_EXPLICIT_GENERAL_PATTERN = re.compile(
    r"\b(?:in general|generally|from general knowledge|as a general question|"
    r"without (?:checking|searching|using) (?:my|our) (?:drive|files?|documents?))\b",
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

_STRUCTURE_INVENTORY_PATTERN = re.compile(
    r"\b(?:how many|number of|count|list|name|names of)\b.{0,60}\b"
    r"(?:sections?|tabs?|worksheets?|chapters?|parts?|headings?)\b|"
    r"\b(?:sections?|tabs?|worksheets?|chapters?|parts?|headings?)\b"
    r".{0,50}\b(?:count|names?|titles?|list)\b",
    re.I,
)


def match_files_by_title(
    query: str, available_files: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Resolve document-title mentions without a Gemini round trip."""
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    ignored_terms = {
        "the", "a", "an", "of", "for", "to", "in", "on", "about", "and",
        "or", "with", "by", "from", "at", "is", "are", "be", "this", "that",
        "these", "those", "my", "our", "your",
    }
    exact_matches = []
    partial_matches = []

    for file_info in available_files:
        title = os.path.splitext(file_info.get("name", ""))[0]
        title_terms = {
            term
            for term in re.findall(r"[a-z0-9]+", title.lower())
            if term not in ignored_terms
        }
        if title_terms and title_terms.issubset(query_terms):
            exact_matches.append(file_info)
        elif title_terms.intersection(query_terms):
            partial_matches.append(file_info)

    return exact_matches[:5] if exact_matches else partial_matches[:5]


def is_document_structure_query(query: str) -> bool:
    """Identify requests that need a whole-document inventory of headings or tabs."""
    return bool(_STRUCTURE_INVENTORY_PATTERN.search(query))


def classify_query_intent(
    query: str, has_selected_files: bool = False
) -> QueryIntent:
    """Classify whether to answer directly or analyze Drive, then shape the response."""
    if any(pattern.search(query) for pattern in _CAPABILITIES_PATTERNS):
        return "capabilities"
    if any(pattern.search(query) for pattern in _ASSISTANT_INFO_PATTERNS):
        return "assistant_info"
    if _DOCUMENT_SEARCH_PATTERN.search(query):
        return "document_search"
    if not has_selected_files and _EXPLICIT_GENERAL_PATTERN.search(query):
        return "direct_answer"

    requires_document_analysis = (
        has_selected_files
        or _DOCUMENT_REQUEST_PATTERN.search(query)
        or _PERSONAL_CONTEXT_PATTERN.search(query)
        or _BUSINESS_DATA_PATTERN.search(query)
        or _TOPIC_RELATION_PATTERN.search(query)
    )
    if not requires_document_analysis:
        return "direct_answer"

    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(query):
            return intent

    if re.match(r"^\s*(what|who|when|where|which|how|is|are|does|do|can)\b", query, re.I):
        return "fact"
    return "general"
