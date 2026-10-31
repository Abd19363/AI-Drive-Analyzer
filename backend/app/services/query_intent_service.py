import os
import re
from typing import Any, Dict, List, Literal

QueryIntent = Literal[
    "capabilities",
    "assistant_info",
    "direct_answer",
    "media",
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
    # General Definitions & Tech Concepts
    re.compile(
        r"^\s*(?:what\s+is|what\s+are|define|definition\s+of|explain|tell\s+me\s+about)\s+(?:a\s+|an\s+|the\s+)?(?:algorithm|artificial\s+intelligence|"
        r"machine\s+learning|deep\s+learning|blockchain|cryptocurrency|http|https|tcp|udp|api|dns|cloud\s+computing|"
        r"operating\s+system|photosynthesis|gravity|entropy|inflation|recession|gross\s+domestic\s+product|gdp|democracy|"
        r"republic|ecosystem|biodiversity|ozone\s+layer|greenhouse\s+effect|black\s+hole|"
        r"python|javascript|typescript|java|c\+\+|golang|rust|ruby|php|swift|react|vue|angular|docker|kubernetes|git|linux|sql)"
        r"(?:\s+(?:programming\s+)?language|\s+framework|\s+library|\s+protocol)?\b[?.!]*\s*$",
        re.I,
    ),
    # General Coding & Programming Tasks
    re.compile(
        r"\b(?:write|create|give\s+me|generate)\s+(?:a\s+)?(?:python|javascript|typescript|java|c\+\+|c\#|sql|html|css|bash|ruby|go|rust)\s+(?:code|script|function|program|query|snippet|algorithm)\b",
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
    query: str,
    available_files: List[Dict[str, Any]],
    minimum_score: int = 1,
) -> List[Dict[str, Any]]:
    """Resolve document-title mentions using scored relevance."""
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

        if score >= minimum_score:
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
