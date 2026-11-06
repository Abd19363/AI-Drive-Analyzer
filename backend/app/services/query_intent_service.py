import os
import re
from typing import Any, Dict, List, Literal

QueryIntent = Literal[
    "capabilities",
    "assistant_info",
    "direct_answer",
    "media",
    "confidential",
    "document_search",
    "drive_inventory",
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

_DRIVE_INVENTORY_PATTERNS = (
    re.compile(
        r"\b(?:check|verify|see|tell\s+me)\s+(?:whether|if)\b.{0,100}\b(?:in|on|inside|within)\s+(?:my\s+|the\s+)?(?:google\s+)?drive\b",
        re.I,
    ),
    re.compile(
        r"^\s*(?:is|are)\s+.{0,100}\b(?:in|on|inside|within)\s+(?:my\s+|the\s+)?(?:google\s+)?drive\b",
        re.I,
    ),
    re.compile(
        r"\bdo\s+i\s+have\b.{0,80}\b(?:in\s+(?:my\s+|the\s+)?(?:google\s+)?drive|\bfile|\bdocument)?\b",
        re.I,
    ),
    re.compile(
        r"\bdoes\s+(?:my\s+|the\s+)?(?:google\s+)?drive\s+(?:have|contain)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:what|which)\s+(?:files?|documents?)\b.{0,40}\b(?:in|on)\s+(?:my\s+|the\s+)?(?:google\s+)?drive\b",
        re.I,
    ),
    re.compile(
        r"\b(?:list|show|display|get)\s+(?:all\s+)?(?:the\s+)?(?:my\s+)?(?:google\s+)?drive\s+files\b",
        re.I,
    ),
    re.compile(
        r"\b(?:list|show|display)\s+(?:all\s+)?(?:the\s+)?files?\s+(?:in|from|on)\s+(?:my\s+|the\s+)?(?:google\s+)?drive\b",
        re.I,
    ),
)

_VAGUE_INVENTORY_TARGETS = {
    "", "it", "this", "that", "the file", "a file", "the files", "files",
    "the document", "a document", "the documents", "documents",
    "the specific file", "specific file", "a specific file",
    "the specific document", "specific document", "a specific document",
    "information", "the information", "specific information", "the specific information",
    "the specific file or information", "specific file or information",
    "file or information", "the file or information",
    "something", "anything", "any files", "any file", "item", "the item",
}


def is_drive_inventory_query(query: str) -> bool:
    """Identify requests that ask about file existence or inventory in Google Drive."""
    return any(p.search(query) for p in _DRIVE_INVENTORY_PATTERNS)


def extract_drive_inventory_target(query: str) -> tuple[str, bool]:
    """
    Analyzes a drive inventory query.
    Returns (target_text, is_vague).
    - If is_vague is True, the query refers to an unspecified item ('it', 'the file', etc.).
    - If target_text is 'LIST_ALL', the user wants a full listing of files in Drive.
    - Otherwise, target_text is the specific filename or keyword to verify in Drive.
    """
    q = query.strip()

    if (
        re.search(r"\b(?:what|which)\s+(?:files?|documents?)\b.{0,30}\b(?:in|on)\s+(?:my\s+|the\s+)?(?:google\s+)?drive\b", q, re.I)
        or re.search(r"\b(?:list|show|display|get)\s+(?:all\s+)?(?:the\s+)?(?:my\s+)?(?:google\s+)?drive\s+files\b", q, re.I)
        or re.search(r"\b(?:list|show|display)\s+(?:all\s+)?(?:the\s+)?files?\s+(?:in|from|on)\s+(?:my\s+|the\s+)?(?:google\s+)?drive\b", q, re.I)
    ):
        return ("LIST_ALL", False)

    m = re.search(
        r"\b(?:check|verify|see|tell\s+me)\s+(?:whether|if)\s+(.+?)\s+(?:is|are|exists?)\s+(?:in|on|inside|within)\s+(?:my\s+|the\s+)?(?:google\s+)?drive",
        q,
        re.I,
    )
    if not m:
        m = re.search(
            r"^\s*(?:is|are)\s+(.+?)\s+(?:in|on|inside|within)\s+(?:my\s+|the\s+)?(?:google\s+)?drive",
            q,
            re.I,
        )
    if not m:
        m = re.search(
            r"\bdo\s+i\s+have\s+(.+?)(?:\s+(?:in|on)\s+(?:my\s+|the\s+)?(?:google\s+)?drive|[?.!,;]|$)",
            q,
            re.I,
        )
    if not m:
        m = re.search(
            r"\bdoes\s+(?:my\s+|the\s+)?(?:google\s+)?drive\s+(?:have|contain)\s+(.+?)(?:[?.!,;]|$)",
            q,
            re.I,
        )

    subject = ""
    if m:
        subject = m.group(1).strip()
        subject = re.sub(r"\s+or\s+not\b.*$", "", subject, flags=re.I).strip()
        subject = re.sub(r"^(?:there\s+)?(?:a\s+|an\s+|any\s+)?", "", subject, flags=re.I).strip()
        subject = re.sub(r"^(?:files?|documents?)\s+(?:named|called|titled)\s+", "", subject, flags=re.I).strip()

    clean_sub = re.sub(r"[^a-z0-9\s]", "", subject.lower()).strip()
    if not clean_sub or clean_sub in _VAGUE_INVENTORY_TARGETS:
        return (subject or "unspecified", True)

    return (subject, False)


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

_GENERAL_KNOWLEDGE_PATTERNS = (
    # Celestial / Space / Astronomy
    re.compile(
        r"\b(?:distance\s+(?:between|from|to)\s+(?:the\s+)?(?:earth|moon|sun|mars|jupiter|saturn|venus|mercury|neptune|uranus|pluto|alpha\s+centauri)|"
        r"speed\s+of\s+(?:light|sound)|solar\s+system|black\s+holes?|galax(?:y|ies)|universe|planets?|stars?|supernovas?|nebula|constellations?|"
        r"orbit\s+of\s+(?:the\s+)?(?:moon|earth|mars)|how\s+far\s+is\s+(?:the\s+)?(?:moon|sun|mars|earth))\b",
        re.I,
    ),
    # Geography / World Facts
    re.compile(
        r"\b(?:capital\s+(?:city\s+)?of|population\s+of|largest\s+(?:country|city|ocean|river|mountain|continent|island|desert)|"
        r"tallest\s+(?:building|mountain|structure|tower)|longest\s+river|deepest\s+ocean|border\s+between|"
        r"where\s+is\s+(?:mount\s+everest|paris|tokyo|london|rome|egypt|brazil|japan|australia|canada|antarctica))\b",
        re.I,
    ),
    # Science / Physics / Chemistry / Biology
    re.compile(
        r"\b(?:photosynthesis|mitochondria|dna|rna|gravity|relativity|quantum(?:\s+mechanics|\s+physics|\s+computing)?|"
        r"thermodynamics|periodic\s+table|atomic\s+(?:number|mass|weight)|chemical\s+formula|water\s+cycle|"
        r"plate\s+tectonics|evolution|natural\s+selection|laws?\s+of\s+motion|speed\s+of\s+gravity)\b",
        re.I,
    ),
    # Historical Figures, Leaders & Celebrated People
    re.compile(
        r"\bwho\s+(?:was|is)\s+(?:the\s+)?(?:first|second|current|16th|44th|45th|46th|[0-9]+(?:st|nd|rd|th))\s+(?:president|prime\s+minister|chancellor|monarch|king|queen|governor|ruler)\b|"
        r"\bwho\s+(?:was|is)\s+(?:albert\s+einstein|isaac\s+newton|william\s+shakespeare|aristotle|plato|socrates|"
        r"leonardo\s+da\s+vinci|galileo(?:\s+galilei)?|charles\s+darwin|marie\s+curie|nikola\s+tesla|thomas\s+edison|"
        r"alexander\s+the\s+great|julius\s+caesar|napoleon(?:\s+bonaparte)?|abraham\s+lincoln|george\s+washington|"
        r"winston\s+churchill|nelson\s+mandela|mahatma\s+gandhi|martin\s+luther\s+king(?:\s+jr)?|steve\s+jobs|bill\s+gates|elon\s+musk)\b",
        re.I,
    ),
    # Inventions & Discoveries
    re.compile(
        r"\bwho\s+(?:invented|discovered|wrote|painted|composed|founded|created)\s+(?:the\s+)?(?:telephone|lightbulb|airplane|internet|"
        r"computer|penicillin|gravity|telescope|electricity|mona\s+lisa|hamlet|radio|world\s+wide\s+web)\b",
        re.I,
    ),
    # Common Trivia & Measurements
    re.compile(
        r"\b(?:tallest\s+animal|largest\s+mammal|fastest\s+animal|how\s+many\s+(?:continents|planets|countries|states|bones\s+in\s+the\s+human\s+body|hours\s+in\s+a\s+day|days\s+in\s+a\s+year|seconds\s+in\s+an?\s+hour))\b",
        re.I,
    ),
    # Pure Math Calculations
    re.compile(
        r"^\s*(?:calculate|what\s+is|solve)\s+[0-9\s\+\-\*\/\^\(\)\.\%]+\s*[?.!]*\s*$",
        re.I,
    ),
)


def is_fast_general_knowledge_query(query: str) -> bool:
    """Instantly detect unambiguous general knowledge queries without Drive access."""
    # Never classify as general if it contains document or personal indicators
    if (
        _DOCUMENT_REQUEST_PATTERN.search(query)
        or _DOCUMENT_SEARCH_PATTERN.search(query)
        or _PERSONAL_CONTEXT_PATTERN.search(query)
        or _BUSINESS_DATA_PATTERN.search(query)
    ):
        return False
    return any(p.search(query) for p in _GENERAL_KNOWLEDGE_PATTERNS)

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
        re.compile(r"\b(list|enumerate|all|every|names of|names and|names|items|candidates?)\b", re.I),
    ),
)

_STRUCTURE_INVENTORY_PATTERN = re.compile(
    r"\b(?:what|which|show|display|list|how many|number of|count|name|names of)\b.{0,60}\b"
    r"(?:sections?|tabs?|worksheets?|sub-?sheets?|sub\s+sheets?|sheets?|chapters?|parts?|headings?)\b|"
    r"\b(?:sections?|tabs?|worksheets?|sub-?sheets?|sub\s+sheets?|sheets?|chapters?|parts?|headings?)\b"
    r".{0,50}\b(?:count|names?|titles?|list|available|contain|in\s+(?:the|this))\b",
    re.I,
)

_SHEET_TERM = r"(?:sub-?sheets?|sub\s+sheets?|worksheets?|sheets?|tabs?)"

_QUOTED_SHEET_PATTERN = re.compile(
    rf"\b(?:in|from|on|within)\s+(?:the\s+)?[\"']([^\"']{{1,100}})[\"']\s+{_SHEET_TERM}\b",
    re.I,
)
_QUOTED_TRAILING_SHEET_PATTERN = re.compile(
    rf"[\"']([^\"']{{1,100}})[\"']\s+{_SHEET_TERM}\b",
    re.I,
)
_NAMED_SHEET_PATTERN = re.compile(
    rf"\b{_SHEET_TERM}\s+(?:named|called|titled)\s+[\"']?(.+?)[\"']?(?=\s+(?:for|about|with|that|to|and|in)\b|[?.!,;]|$)",
    re.I,
)
_PREFIXED_SHEET_PATTERN = re.compile(
    rf"\b(?:in|from|on|within)\s+(?:the\s+)?{_SHEET_TERM}\s*(?::|=|\s)\s*[\"']?([a-zA-Z0-9_\-\s]+?)[\"']?(?=\s+(?:for|about|with|that|to|and|in)\b|[?.!,;]|$)",
    re.I,
)
_TRAILING_SHEET_PATTERN = re.compile(
    rf"\b(?:in|from|on|within)\s+(?:the\s+)?[\"']?([a-zA-Z0-9][a-zA-Z0-9 _&-]{{0,80}}?)\s+{_SHEET_TERM}\b",
    re.I,
)
_IMPLICIT_SHEET_REQUEST_PATTERNS = (
    re.compile(
        r"^\s*(?:give me|show me|get me|summari[sz]e|explain|describe|"
        r"tell me about)\s+(.+?)\s*[?.!]*\s*$",
        re.I,
    ),
)

_SHEET_GENERIC_WORDS = {
    "the", "this", "that", "a", "an", "all", "each", "every",
    "excel", "file", "files", "workbook", "workbooks", "sheet", "sheets",
    "subsheet", "subsheets", "sub-sheet", "sub-sheets", "tab", "tabs",
}


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
            if name and name.lower() not in _SHEET_GENERIC_WORDS:
                return name

    sheet_marker = re.search(r"\b(?:sub-?sheets?|sub\s+sheets?|worksheets?|sheets?|tabs?)\b", query, re.I)
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
            if name and name.lower() not in _SHEET_GENERIC_WORDS and len(name) <= 100 and len(name.split()) <= 8:
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
    query: str,
    available_files: List[Dict[str, Any]],
    minimum_score: int = 1,
) -> List[Dict[str, Any]]:
    """Resolve document-title and folder mentions using scored keyword relevance."""
    ignored = {
        "the", "a", "an", "of", "for", "to", "in", "on", "about", "and",
        "or", "with", "by", "from", "at", "is", "are", "be", "this", "that",
        "these", "those", "my", "our", "your", "give", "me", "show", "tell",
        "what", "who", "when", "where", "how", "can", "you", "please",
        "would", "could", "should", "do", "does", "did", "as", "into",
        "having", "have", "had", "been", "was", "were", "it", "its",
    }
    q_tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in ignored and len(t) >= 2]
    if not q_tokens:
        return []

    q_nums = [t for t in q_tokens if t.isdigit()]
    scored = []
    has_folder_keyword = bool(re.search(r"\b(?:folders?|directories|directory)\b", query, re.I))

    for file_info in available_files:
        name = file_info.get("name", "")
        if not name:
            continue
        is_folder = (
            file_info.get("mimeType") == "application/vnd.google-apps.folder"
            or file_info.get("is_folder", False)
        )
        base_name = os.path.splitext(name)[0].lower() if not is_folder else name.lower()
        file_tokens = set(re.findall(r"[a-z0-9]+", base_name))

        score = 0
        matched_tokens = []
        for qt in q_tokens:
            if qt in file_tokens:
                weight = 40 if qt.isdigit() else (25 if len(qt) >= 4 else 15)
                score += weight
                matched_tokens.append(qt)
            elif any(qt in ft for ft in file_tokens if len(qt) >= 3):
                score += 12
                matched_tokens.append(f"~{qt}")
            elif any(ft in qt for ft in file_tokens if len(ft) >= 4):
                score += 10
                matched_tokens.append(f"<{qt}")

        # Heavy boost for exact numerical codes like '116' in NA-116
        for num in q_nums:
            if num in file_tokens:
                score += 40
            elif any(num in ft for ft in file_tokens):
                score += 25

        # Consecutive phrase match bonus (e.g. 'full stack roadmap' or 'form 33')
        clean_f = re.sub(r"[^a-z0-9]+", " ", base_name)
        for i in range(len(q_tokens) - 1):
            pair = f"{q_tokens[i]} {q_tokens[i+1]}"
            if pair in clean_f:
                score += 30

        # Substring word boundary bonus
        for qt in q_tokens:
            if len(qt) >= 3 and re.search(r"\b" + re.escape(qt) + r"\b", clean_f):
                score += 10

        # Folder relevance boost when user mentions folder
        if is_folder and has_folder_keyword and score > 0:
            score += 20

        # Light penalty for huge files (> 25MB) only when other files match
        size = file_info.get("size")
        if size and int(size) > 25 * 1024 * 1024:
            score -= 10

        if score >= minimum_score:
            scored.append((score, file_info))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Return top highest-scoring files or folders
    return [item[1] for item in scored[:5]]


def is_document_structure_query(query: str) -> bool:
    """Identify requests that need a whole-document inventory of headings or tabs."""
    return bool(_STRUCTURE_INVENTORY_PATTERN.search(query))


_CONSTITUENCY_PATTERN = re.compile(
    r"\b(?:constituency\s+(?:na|pp|pk|ps)\s*[-–—_]?\s*\d+|(?:na|pp|pk|ps)\s*[-–—_]?\s*\d+)\b",
    re.I,
)


def _extract_constituency_codes(text: str) -> set:
    """Extract normalized constituency codes (e.g. {'na-116', 'pp-55'}) from query or file name."""
    if not text:
        return set()
    matches = re.findall(
        r"(?i)(?:^|[^a-z0-9])(na|pp|pk|ps)\s*[-–—_]?\s*(\d+)(?:$|[^a-z0-9])",
        text,
    )
    return {f"{prefix.lower()}-{num}" for prefix, num in matches}


def is_constituency_data_query(query: str) -> bool:
    """Identify requests asking for election constituency candidates, Form-33, or symbols."""
    return bool(_CONSTITUENCY_PATTERN.search(query))


def is_specific_record_query(query: str) -> bool:
    """Identify requests asking for specific records, forms, IDs, candidates, or documents."""
    return is_constituency_data_query(query) or bool(
        re.search(
            r"\b(?:form\s*[-–—_]?\s*\d+|invoices?|receipts?|salary\s+slip|cnic|passport|contracts?|nda|specifications?|requirements?|roadmaps?|syllab(?:us|i)|curricul(?:um|a))\b",
            query,
            re.I,
        )
    )


def filter_files_by_query_scope(
    query: str, files: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    If the query mentions a specific constituency code (e.g. NA-116),
    filter candidate files so that only files matching that constituency code
    are kept, preventing pollution from other constituencies.
    """
    if not files:
        return files

    m = re.search(r"\b(na|pp|pk|ps)\s*[-–—]?\s*(\d+)\b", query, re.I)
    if not m:
        return files

    prefix = m.group(1).lower()
    num = m.group(2)
    target_tokens = [f"{prefix}-{num}", f"{prefix}_{num}", f"{prefix} {num}", num]

    filtered = []
    for f in files:
        fname = (f.get("name") or "").lower()
        if any(tok in fname for tok in target_tokens):
            filtered.append(f)

    return filtered if filtered else files


def classify_query_intent(
    query: str, has_selected_files: bool = False
) -> QueryIntent:
    """Classify whether to answer directly or analyze Drive, then shape the response."""
    if any(pattern.search(query) for pattern in _CAPABILITIES_PATTERNS):
        return "capabilities"
    if any(pattern.search(query) for pattern in _ASSISTANT_INFO_PATTERNS):
        return "assistant_info"
    if is_drive_inventory_query(query):
        return "drive_inventory"
    if _DOCUMENT_SEARCH_PATTERN.search(query):
        return "document_search"
    if not has_selected_files and _EXPLICIT_GENERAL_PATTERN.search(query):
        return "direct_answer"

    # Fast general knowledge detection (science, astronomy, trivia, coding, definitions, etc.)
    if not has_selected_files and is_fast_general_knowledge_query(query):
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

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs (includes 📄, 📊, etc.)
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols, etc.
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"  # misc symbols
    "]+",
    flags=re.UNICODE,
)


def clean_response_text(text: str) -> str:
    """
    Cleans response text ensuring:
    1. No outer markdown fences (```markdown / ```) or wrapping quotes.
    2. No emojis or decorative pictographs (📄, 📊, 🔍, etc.).
    3. No lines wrapped entirely in asterisks (**text** on a full line).
    4. No orphan asterisks, hyphens, or special character lines.
    5. Clean start and end of each line (no stray punctuation/special characters).
    6. Clean start and end of the entire response (no leading/trailing quotes, symbols, or fences).
    """
    if not text:
        return ""

    cleaned = text.strip()

    # 1. Remove outer code fence wrappers
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

    # 2. Strip outer enclosing quotes
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()

    # 3. Strip all emojis
    cleaned = EMOJI_PATTERN.sub("", cleaned)

    # 4. Clean line by line
    cleaned_lines = []
    for raw_line in cleaned.splitlines():
        line = raw_line.rstrip()

        # Remove zero-width and invisible characters
        line = re.sub(r"[\u200b\u200e\u200f\ufeff]", "", line)

        # Skip lines that are purely special characters (e.g. ***, ---, **, __, ===)
        if re.match(r"^[\s\*\-\_\~\#\=\:\;]+$", line):
            continue

        # If an entire line is wrapped in double asterisks, unwrap it (e.g. **Heading** -> Heading)
        m_bold = re.match(r"^\s*\*\*(.+?)\*\*\s*$", line)
        if m_bold:
            line = m_bold.group(1).strip()

        # If an entire line is wrapped in single asterisks, unwrap it (e.g. *Heading* -> Heading)
        m_italic = re.match(r"^\s*\*(.+?)\*\s*$", line)
        if m_italic:
            line = m_italic.group(1).strip()

        # If a line is wrapped in quotes, unwrap it
        m_quote = re.match(r'^\s*["\'](.+?)["\']\s*$', line)
        if m_quote:
            line = m_quote.group(1).strip()

        # Remove trailing backslashes or orphan asterisks at end of line
        line = re.sub(r"[\\]+$", "", line).rstrip()
        line = re.sub(r"(?<!\*)\*$", "", line).rstrip()

        # Normalize multiple spaces after bullets or numbers
        line = re.sub(r"^(\s*[-*])\s{2,}", r"\1 ", line)
        line = re.sub(r"^(\s*\d+\.)\s{2,}", r"\1 ", line)

        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines).strip()

    # 5. Clean start and end of the entire response:
    strip_chars = "`*\"'~_#:\\ \t\r\n"
    result = result.strip(strip_chars)

    return result
