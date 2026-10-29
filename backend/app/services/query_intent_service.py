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

_QUOTED_SHEET_PATTERN = re.compile(
    r"\b(?:in|from|on|within)\s+(?:the\s+)?[\"']([^\"']{1,100})[\"']\s+"
    r"(?:sheet|tab|worksheet)\b",
    re.I,
)
_QUOTED_TRAILING_SHEET_PATTERN = re.compile(
    r"[\"']([^\"']{1,100})[\"']\s+(?:sheet|tab|worksheet)\b",
    re.I,
)
_NAMED_SHEET_PATTERN = re.compile(
    r"\b(?:sheet|tab|worksheet)\s+(?:named|called|titled)\s+"
    r"[\"']?(.+?)[\"']?(?=\s+(?:for|about|with|that|to|and)\b|[?.!,;]|$)",
    re.I,
)
_PREFIXED_SHEET_PATTERN = re.compile(
    r"\b(?:in|from|on|within)\s+(?:the\s+)?"
    r"(?:sheet|tab|worksheet)\s*(?::|=)?\s*[\"']?(.+?)[\"']?"
    r"(?=\s+(?:for|about|with|that|to|and)\b|[?.!,;]|$)",
    re.I,
)
_TRAILING_SHEET_PATTERN = re.compile(
    r"\b(?:in|from|on|within)\s+(?:the\s+)?"
    r"[\"']?([a-z0-9][a-z0-9 _&-]{0,80}?)\s+"
    r"(?:sheet|tab|worksheet)\b",
    re.I,
)
_IMPLICIT_SHEET_REQUEST_PATTERNS = (
    re.compile(
        r"^\s*(?:give me|show me|get me|summari[sz]e|explain|describe|"
        r"tell me about)\s+(.+?)\s*[?.!]*\s*$",
        re.I,
    ),
)


def requested_sheet_name(query: str) -> str | None:
    """Return a clearly specified worksheet name, without guessing from topics."""
    for pattern in (
        _QUOTED_SHEET_PATTERN,
        _NAMED_SHEET_PATTERN,
        _PREFIXED_SHEET_PATTERN,
        _TRAILING_SHEET_PATTERN,
        _QUOTED_TRAILING_SHEET_PATTERN,
    ):
        match = pattern.search(query)
        if match:
            name = match.group(1).strip().strip("\"' ")
            if name:
                return name

    sheet_marker = re.search(r"\b(?:sheet|tab|worksheet)\b", query, re.I)
    if sheet_marker:
        prefix = query[:sheet_marker.start()]
        for marker in reversed(list(re.finditer(
            r"\b(?:the|in|from|on|within)\s+",
            prefix,
            re.I,
        ))):
            name = prefix[marker.end():].strip().strip("\"' ")
            if name.lower().startswith("the "):
                name = name[4:].strip()
            if name and len(name) <= 100 and len(name.split()) <= 8:
                return name
    return None


def implicit_sheet_name_candidate(query: str) -> str | None:
    """Extract a likely sheet title from a short imperative query."""
    for pattern in _IMPLICIT_SHEET_REQUEST_PATTERNS:
        match = pattern.search(query)
        if match:
            candidate = match.group(1).strip().strip("\"' ")
            if candidate.lower().startswith("the "):
                candidate = candidate[4:].strip()
            return candidate or None
    return None


def match_files_by_title(
    query: str, available_files: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Resolve document-title mentions accurately using scored relevance."""
    ignored = {
        "the", "a", "an", "of", "for", "to", "in", "on", "about", "and",
        "or", "with", "by", "from", "at", "is", "are", "be", "this", "that",
        "these", "those", "my", "our", "your", "give", "me", "show", "tell",
        "what", "who", "when", "where", "how", "can", "you", "please",
        "questions", "question", "names", "name", "contesting", "candidates", "candidate",
    }
    q_tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in ignored]
    if not q_tokens:
        return []

    q_nums = [t for t in q_tokens if t.isdigit()]
    scored = []

    for file_info in available_files:
        name = file_info.get("name", "")
        is_folder = file_info.get("mimeType") == "application/vnd.google-apps.folder"
        base_name = os.path.splitext(name)[0].lower()
        file_tokens = set(re.findall(r"[a-z0-9]+", base_name))

        score = 0
        matched_tokens = []
        for qt in q_tokens:
            if qt in file_tokens:
                weight = 25 if (qt in q_nums or len(qt) >= 5) else 10
                score += weight
                matched_tokens.append(qt)
            elif any(qt in ft for ft in file_tokens if len(qt) >= 4):
                score += 5
                matched_tokens.append(f"~{qt}")

        # Heavy boost for exact numerical codes like '116' in NA-116
        for num in q_nums:
            if num in file_tokens:
                score += 50
            elif any(num in ft for ft in file_tokens):
                score += 30

        # Substring phrase match bonus
        clean_f = re.sub(r"[^a-z0-9]+", " ", base_name)
        for qt in q_tokens:
            if len(qt) >= 3 and re.search(r"\b" + re.escape(qt) + r"\b", clean_f):
                score += 15

        # Penalize pure folders when individual documents match
        if is_folder:
            score -= 20

        # Penalize huge textbook-like files (> 15MB) when other documents match
        size = file_info.get("size")
        if size and int(size) > 15 * 1024 * 1024:
            score -= 10

        if score > 0:
            scored.append((score, file_info))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Return top 2-3 highest-scoring files
    return [item[1] for item in scored[:3]]


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

    # Conversational greetings or casual small talk that should not query Drive
    if not has_selected_files and re.match(
        r"^\s*(?:hi|hello|hey|howdy|greetings|good\s+(?:morning|afternoon|evening|day)|how\s+are\s+you|who\s+are\s+you|tell\s+me\s+a\s+joke)\b[?.!]*\s*$",
        query,
        re.I,
    ):
        return "direct_answer"

    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(query):
            return intent

    if re.match(r"^\s*(what|who|when|where|which|how|is|are|does|do|can)\b", query, re.I):
        return "fact"
    return "general"
