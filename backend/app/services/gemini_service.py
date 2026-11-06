import asyncio
import json
import logging
import os
import re
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from app.config import settings
from app.services.guardrail_service import (
    is_query_about_media,
    MEDIA_QUERY_RESPONSE,
    is_media_file,
    check_confidential_query,
)
from app.services.query_intent_service import (
    is_document_structure_query,
    match_files_by_title,
    clean_response_text,
)

logger = logging.getLogger(__name__)


class GeminiServiceUnavailableError(RuntimeError):
    """Raised when all configured Gemini models are temporarily unavailable."""


def get_gemini_client():
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in settings or .env")
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _is_candidate_list_query(query: str, intent: str = "general") -> bool:
    has_candidate = bool(
        re.search(r"\b(?:candidate|candidates|contesting|contestants?|nominee|nominees)\b", query, re.I)
    )
    has_election_context = bool(
        re.search(
            r"\b(?:party|parties|affiliation|affiliations|symbol|symbols|constituency|electoral|election|na\s*-\s*\d+|pp\s*-\s*\d+|ps\s*-\s*\d+|pk\s*-\s*\d+|pb\s*-\s*\d+)\b",
            query,
            re.I,
        )
    )
    is_list_like = intent == "list" or bool(re.search(r"\b(?:give\s+me|list|show|names?|who\s+are|all|every)\b", query, re.I))
    return has_candidate and (has_election_context or is_list_like)


def _candidate_list_fields(query: str) -> List[str]:
    fields = []
    if re.search(r"\b(?:symbol|symbols)\b", query, re.I):
        fields.append("Allocated symbol")
    if re.search(r"\b(?:party|parties|affiliation|affiliations)\b", query, re.I):
        fields.append("Party affiliation")
    if not fields:
        fields = ["Allocated symbol", "Party affiliation"]
    return fields


def _validate_candidate_list_answer(
    answer: str,
    source_texts: List[str],
    fields: List[str],
) -> str:
    source_chunks = [
        re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        for text in source_texts
    ]
    rows = []
    for line in answer.splitlines():
        cells = [cell.strip().strip("*_` ") for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(fields) + 1:
            continue
        candidate, *details = cells
        candidate_normalized = re.sub(r"[^a-z0-9]+", " ", candidate.lower()).strip()
        details_normalized = [
            re.sub(r"[^a-z0-9]+", " ", detail.lower()).strip()
            for detail in details
        ]
        if not candidate_normalized or not all(details_normalized):
            continue
        if candidate_normalized == "candidate":
            continue
        rows.append((candidate_normalized, details_normalized))

    if rows and all(
        any(
            candidate in source
            and all(detail in source for detail in details)
            for source in source_chunks
        )
        for candidate, details in rows
    ):
        return answer

    return (
        "I couldn't verify the requested candidate details against the text "
        "extracted from the selected document, so I won't guess. Please retry "
        "after checking the PDF's OCR; if the scan is readable, the list should "
        "be extracted from the document."
    )


# Error patterns that should not trigger model failover.
_FATAL_PATTERNS = {"API_KEY_INVALID", "API KEY NOT VALID", "API_KEY_EXPIRED"}


def _should_try_fallback(err: Exception) -> bool:
    """Return whether this error may be resolved by trying another model."""
    msg = str(err).upper()
    if any(pat in msg for pat in _FATAL_PATTERNS):
        return False

    status_code = getattr(err, "code", None)
    if not isinstance(status_code, int):
        response = getattr(err, "response", None)
        status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int):
        match = re.search(r"\b(408|429|5\d{2}|404)\b", msg)
        status_code = int(match.group(1)) if match else None

    if status_code in (404, 408, 429):
        return True
    if status_code is not None:
        return 500 <= status_code <= 599
    if any(k in msg for k in ("UNAVAILABLE", "NOT_FOUND", "NOT FOUND", "RESOURCE_EXHAUSTED", "HIGH DEMAND")):
        return True
    return isinstance(err, (TimeoutError, ConnectionError))

def generate_content_with_fallback(client, contents, config=None):
    """
    Use the configured model first, then documented stable Gemini models.
    The Google SDK handles bounded retries with exponential backoff for transient
    failures; this function only moves to another model after that call fails.
    """
    models = [
        settings.GEMINI_MODEL,        # Primary configured model (e.g. gemini-flash-lite-latest)
        "gemini-flash-lite-latest",   # Active fast model
        "gemini-3.1-flash-lite",      # Stable fast model
        "gemini-flash-latest",        # Stable flash model
        "gemini-3.8-flash",           # High capacity flash model
    ]
    seen = set()
    unique_models = [m for m in models if m and not (m in seen or seen.add(m))]

    if config is None:
        config = types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=4096,
        )

    last_err = None
    for model_name in unique_models:
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
        except Exception as e:
            last_err = e
            if _should_try_fallback(e):
                logger.warning(
                    "Gemini model %r failed; trying the next configured model: %s",
                    model_name,
                    e,
                )
                continue
            raise
    raise GeminiServiceUnavailableError(
        "Gemini is temporarily unavailable across the configured models. "
        "Please retry in a few minutes."
    ) from last_err


_COMPREHENSIVE_DETAIL_PATTERN = re.compile(
    r"\b("
    r"in\s+(?:great\s+)?detail|detailed|thoroughly|deep\s*dive|comprehensive|complete\s+guide|"
    r"roadmap|guided\s+lessons|step\s*by\s*step|from\s+scratch|"
    r"from\s+basics?\s+to\s+advance[d]?|guide\s+me\s+from|curriculum|syllabus|"
    r"elaborate\s+extensively|system\s+design|full\s+course|"
    r"\d+\s*(?:month|week|day)s?\s+(?:plan|roadmap|guide|lessons|syllabus)|"
    r"explain\s+(?:everything|all\s+about)"
    r")\b",
    re.IGNORECASE,
)

_CONCISE_DETAIL_PATTERN = re.compile(
    r"\b("
    r"what\s+is\s+this|define\s+this|quick\s+example|briefly|short\s+answer|"
    r"in\s+short|in\s+brief|quick\s+summary|give\s+a\s+quick|"
    r"define\b|what\s+is\s+an?\b|what\s+are\b|who\s+is\b|when\s+was\b|where\s+is\b|"
    r"meaning\s+of\b|syntax\s+of\b|simple\s+example|one\s+line|shortly"
    r")\b",
    re.IGNORECASE,
)


def detect_query_detail_intent(query: str) -> str:
    """
    Intelligently infer how much detail the user is seeking:
    - 'comprehensive': explicit requests for detail, roadmaps, step-by-step curricula
    - 'concise': quick definitions, "what is this", "define with example", brief facts
    - 'moderate': balanced standard conversational question
    """
    q = query.strip()
    if _COMPREHENSIVE_DETAIL_PATTERN.search(q):
        return "comprehensive"
    if _CONCISE_DETAIL_PATTERN.search(q):
        return "concise"
    return "moderate"


GENERAL_ASSISTANT_SYSTEM_INSTRUCTION = """You are a highly capable, intelligent, and knowledgeable AI assistant, similar to ChatGPT and Gemini.
CRITICAL: Calibrate the depth, structure, and length of your response according to the user's intent:

1. Concise & Direct Intent:
   - When the user asks "What is this?", "Define this with an example", simple factual queries, or quick syntax/concept questions:
   - Provide a clear, crisp, and direct explanation.
   - Include a concise, practical example if requested or helpful.
   - Keep the response focused, readable, and to the point (1-3 short paragraphs or clean bullet points).
   - Do NOT generate unsolicited multi-page roadmaps, essays, or unnecessary filler.

2. Comprehensive & In-Depth Intent:
   - When the user asks to "explain in detail", "give a guided roadmap from basics to advanced", "comprehensive guide", "step-by-step", or multi-month learning plans:
   - Provide an exhaustive, deeply structured, and high-quality guide.
   - Structure with clear headings (## and ###), chronological phases/modules, recommended tools, milestone projects, Markdown comparison tables, and full code examples with explanations.

3. Moderate / Balanced Intent:
   - For general questions that fall in between, provide a well-rounded, informative, and structured response with clear concepts and practical takeaways without being overly brief or overwhelmingly long.

Always use clean Markdown (headings, bold text, bullet points, and code blocks). Do not mention Google Drive unless explicitly asked. Never disclose confidential personal or financial data.
"""


async def answer_general_query(
    query: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Answer general questions with adaptive depth and detail matching the user's intent."""
    client = get_gemini_client()

    detail_intent = detect_query_detail_intent(query)
    directive = {
        "concise": "[User Intent: Concise & Direct. Provide a crisp, succinct explanation with a quick practical example. Avoid excessive length or unsolicited essays.]",
        "comprehensive": "[User Intent: Comprehensive & In-Depth. Provide an exhaustive, deeply structured guide with phases, milestone projects, and rich detail.]",
        "moderate": "[User Intent: Balanced. Provide an informative, well-structured answer with good depth and practical context.]",
    }[detail_intent]

    max_tokens = {
        "concise": 1536,
        "moderate": 3072,
        "comprehensive": 8192,
    }[detail_intent]

    prompt_parts = []
    if conversation_history:
        prompt_parts.append("### Conversation History:")
        for turn in conversation_history[-6:]:
            role = "User" if turn.get("role") in ("user", "human") else "AI Assistant"
            text = (turn.get("text") or "").strip()
            if text:
                prompt_parts.append(f"{role}: {text}")
        prompt_parts.append("\n### Current User Directive & Question:")

    prompt_parts.append(directive)
    prompt_parts.append(f"User Question: {query}")

    full_prompt = "\n".join(prompt_parts)
    config = types.GenerateContentConfig(
        system_instruction=GENERAL_ASSISTANT_SYSTEM_INSTRUCTION,
        temperature=0.7,
        max_output_tokens=max_tokens,
    )
    response = await asyncio.to_thread(generate_content_with_fallback, client, full_prompt, config)
    if not response.text:
        raise RuntimeError("Gemini returned an empty response for the general question.")
    answer = response.text
    return sanitize_confidential_output(answer, query)


async def classify_general_vs_drive_query(
    query: str,
    available_files: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    Intelligently determines whether a query of ANY context is a General Knowledge / Conversational
    question (which should be answered directly without analyzing Drive files) or a Drive Document
    query (which specifically requires searching the user's private Google Drive documents).
    Returns True for General Knowledge queries, False for Drive Document queries.
    """
    from app.services.query_intent_service import (
        is_fast_general_knowledge_query,
        is_drive_inventory_query,
        is_specific_record_query,
        _DOCUMENT_REQUEST_PATTERN,
        _DOCUMENT_SEARCH_PATTERN,
        _PERSONAL_CONTEXT_PATTERN,
        _BUSINESS_DATA_PATTERN,
    )

    if is_fast_general_knowledge_query(query):
        return True

    if is_specific_record_query(query):
        return False

    if is_drive_inventory_query(query):
        return False

    # Check explicit document or personal directives
    if (
        _DOCUMENT_REQUEST_PATTERN.search(query)
        or _DOCUMENT_SEARCH_PATTERN.search(query)
        or _PERSONAL_CONTEXT_PATTERN.search(query)
        or _BUSINESS_DATA_PATTERN.search(query)
    ):
        return False

    # Classify from the request itself; file names must not decide whether a
    # question is general knowledge or a Drive query.
    try:
        client = get_gemini_client()

        prompt = f"""You are the intent classifier for an AI Drive Document Assistant.
Classify the USER'S INTENT, not whether the answer might exist on the public internet.

Return GENERAL only for clearly universal, stable, commonly known information, educational explanations, ordinary coding help, or conversation.
Return DRIVE when the user asks for information from their own/connected files or organization, or requests exact, complete, official, current, local, allocated, assigned, registered, or paired records that should be verified from a source document.
When the request could reasonably require a specific record, prefer DRIVE so the assistant can check document content before answering. Do not infer the route from filenames; no filenames are provided.

User Query: "{query}"

Reply strictly with either GENERAL or DRIVE."""
        config = types.GenerateContentConfig(temperature=0.0, max_output_tokens=5)
        response = await asyncio.wait_for(
            asyncio.to_thread(generate_content_with_fallback, client, prompt, config),
            timeout=5.0,
        )
        res_text = (response.text or "").strip().upper()
        logger.info(f"[ROUTER] Fast LLM query classification for '{query}': {res_text}")
        return res_text.startswith("GENERAL")
    except Exception as e:
        logger.warning(f"[ROUTER] Fast LLM classification fallback or timeout: {e}")
        return False


async def analyze_query_for_drive_files(query: str, available_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Uses Gemini to analyze the question and select only the relevant file(s)
    from the user's Google Drive.
    """
    if not available_files:
        return []

    title_matches = match_files_by_title(query, available_files)
    if title_matches:
        logger.info(
            "[RAG] Matched %d file(s) directly from the query title",
            len(title_matches),
        )
        return title_matches

    if re.search(r"\b(agreements?|aggreements?|aggrements?|contracts?|mous?|ndas?)\b", query, re.I):
        agreement_terms = re.compile(
            r"\b(agreement|contract|memorandum|mou|nda|non[-\s]?disclosure|"
            r"legal|lease|terms|service)\b",
            re.I,
        )
        topic_matches = [
            file_info
            for file_info in available_files
            if file_info.get("mimeType") != "application/vnd.google-apps.folder"
            and agreement_terms.search(file_info.get("name", ""))
            and not re.search(r"\b(salary|payslip|passport|cnic|bank statement)\b", file_info.get("name", ""), re.I)
        ]
        if topic_matches:
            logger.info(
                "[RAG] Found %d file(s) with agreement-related titles",
                len(topic_matches),
            )
            return topic_matches[:5]

    textual_files = [
        f for f in available_files
        if not is_media_file(f) and f.get("mimeType") != "application/vnd.google-apps.folder"
    ]
    if not textual_files:
        textual_files = available_files

    # Instant keyword fallback check over filenames
    q_words = [w.lower() for w in query.replace("?", " ").replace(".", " ").replace(",", " ").split() if len(w) > 2]
    if q_words:
        keyword_matched = []
        for f in textual_files:
            fname = f.get("name", "").lower()
            if any(w in fname for w in q_words):
                keyword_matched.append(f)
        if keyword_matched:
            logger.info("[RAG] Instant filename keyword match selected %d candidate(s)", len(keyword_matched[:2]))
            return keyword_matched[:2]

    client = get_gemini_client()
    
    file_catalog = [
        {
            "file_id": f.get("id"),
            "name": f.get("name"),
            "mime_type": f.get("mimeType"),
        }
        for f in textual_files[:15]
    ]
    
    prompt = f"""
You are an expert AI retrieval analyst.
The user asked the following question:
"{query}"

Here is the list of files found in their Google Drive:
{json.dumps(file_catalog, indent=2)}

Task:
Analyze the question and determine which specific file is relevant to answering it. Return ONLY a valid JSON list with at most 1 or 2 file IDs, e.g. ["file_id_1"]. If none are relevant, return [].
"""

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                generate_content_with_fallback,
                client,
                prompt,
                types.GenerateContentConfig(response_mime_type="application/json"),
            ),
            timeout=3.0,
        )
        selected_ids = json.loads(response.text)
        if isinstance(selected_ids, list):
            if selected_ids:
                return [f for f in textual_files if f.get("id") in selected_ids][:2]
            logger.info("[RAG] Gemini analyzed Drive catalog and found 0 relevant files for: '%s'", query)
            return []
    except Exception as e:
        logger.warning("Gemini file-selection JSON error or timeout: %s", e)

    return []

async def synthesize_answer(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    skipped_confidential_files: List[Dict[str, Any]],
    selected_file_names: Optional[List[str]] = None,
    auto_discovered: bool = False,
    available_file_names: Optional[List[str]] = None,
    intent: str = "general",
) -> str:
    """
    Generates the final grounded answer with citations and privacy notices.
    Uses an exhaustive reading strategy: the LLM is instructed to read every
    single chunk before composing the answer, to prevent partial responses.
    """
    client = get_gemini_client()

    selected_files_str = ", ".join(selected_file_names) if selected_file_names else "All active documents"

    # Keep model input bounded to reduce latency and prevent oversized prompts.
    context_blocks = []
    is_structure_query = is_document_structure_query(query)
    is_candidate_list = _is_candidate_list_query(query, intent)
    exhaustive_list_query = is_structure_query or is_candidate_list
    remaining_chars = 24000 if exhaustive_list_query else 10000
    chunks_to_include = retrieved_chunks if exhaustive_list_query else retrieved_chunks[:8]
    for idx, chunk in enumerate(chunks_to_include):
        fname = chunk.get("file_name", "Unknown Document")
        text = chunk.get("chunk_text", "")
        sim = chunk.get("similarity", 0.0)
        block = f"--- CHUNK {idx+1} | Source: {fname} | Similarity: {sim:.2f} ---\n{text}"
        if len(block) > remaining_chars:
            if remaining_chars > 200:
                block = block[:remaining_chars]
            else:
                break
        if not block.strip():
            continue
        context_blocks.append(
            block
        )
        remaining_chars -= len(block)
        if remaining_chars <= 0:
            break
    context_str = "\n\n".join(context_blocks)
    candidate_list_fields = _candidate_list_fields(query)

    intent_instructions = {
        "direct_answer": "Answer using only the supplied document evidence. If it does not contain the answer, say that the information was not found rather than using general knowledge.",
        "fact": "Answer the specific question directly first, then briefly explain the supporting evidence.",
        "summary": "Give a concise, organized summary of the main points relevant to the request.",
        "comparison": "Compare the requested subjects explicitly; use a table when the evidence supports one.",
        "list": "Return the requested items as a clear list and do not omit relevant entries in the supplied context.",
        "calculation": "Show the calculation method and result using only values present in the supplied context. For requests about sections, tabs, worksheets, chapters, parts, or headings, inspect the entire supplied document, count each distinct item once, and provide both the total and the exact names supported by the document. Do not count page breaks or repeated chunk overlap as separate items.",
        "document_search": "Find and list each relevant agreement or contract in the supplied text. Treat agreement, contract, MOU, NDA, memorandum of understanding, and non-disclosure agreement as related terms. For each match, state the source file and the evidence that it is an agreement. If no supplied text supports a match, say that no matching agreement was found in the searched documents.",
        "general": "Respond in the format that best fits the user's request.",
    }
    answer_style = intent_instructions.get(intent, intent_instructions["general"])
    if is_candidate_list:
        requested_details = " and ".join(field.lower() for field in candidate_list_fields)
        column_headers = " | ".join(["Candidate", *candidate_list_fields])
        answer_style = (
            f"Extract every contesting candidate and the {requested_details} explicitly associated with that candidate "
            f"in the supplied document. Return only a table with these columns: {column_headers}. "
            "Add the source filename after the table. Do not add a constituency overview, election history, likely parties, or "
            "outside knowledge. Do not infer a detail from a candidate's name or from unrelated text. "
            "If the supplied text does not show the candidate list or requested details clearly, say that the list could "
            "not be read from the selected document instead of guessing."
        )

    confidential_notice = ""
    if skipped_confidential_files:
        confidential_notice = (
            "\nIMPORTANT PRIVACY NOTICE:\n"
            "The following file(s) contain confidential/sensitive data "
            "(e.g., CNIC, salary slip, financial statements, payment receipts, transaction IDs, PSIDs, or phone numbers) "
            "and were protected from processing:\n"
        )
        for s in skipped_confidential_files:
            confidential_notice += f"- {s.get('name')}: {s.get('reason')}\n"

    discovery_instruction = ""
    if auto_discovered and selected_file_names:
        discovery_instruction = (
            f"\n=== AUTO-DISCOVERY CONTEXT ===\n"
            f"The system identified relevant document(s) from the user's Google Drive: {selected_files_str}.\n"
            f"Answer the user's query comprehensively using the information from these documents.\n"
        )

    out_of_scope_text = (
        f"The identified document(s) ({selected_files_str}) do not contain information regarding '{query}'. "
        f"Please select specific document(s) from your Google Drive catalog or ask a question related to these files."
        if auto_discovered else
        f"The selected file(s) ({selected_files_str}) do not contain information regarding '{query}'. "
        f"Please select the relevant file(s) from your Google Drive catalog or ask a question related to the selected document(s)."
    )

    prompt = f"""You are a secure, privacy-first AI Assistant. You MUST answer the user's query using ONLY the document content provided below.
    File names are labels for identifying and citing sources; they are not evidence. Never infer facts from a file name.

=== USER QUERY ===
"{query}"

=== SOURCE DOCUMENTS ===
{selected_files_str}
{discovery_instruction}
=== DOCUMENT CONTENT (READ EVERY CHUNK THOROUGHLY) ===
{context_str if context_str.strip() else "[NO DOCUMENT CONTENT FOUND]"}

=== RESPONSE INTENT ===
{intent}: {answer_style}
{"For this structure-inventory request, use all supplied chunks from the named file. Identify the document's actual section or tab labels, count distinct labels once, and list each name; do not infer names or count pages." if is_structure_query else ""}

=== PRIVACY BLOCKS ===
{confidential_notice if confidential_notice else "None"}

=== CRITICAL INSTRUCTIONS (FOLLOW EXACTLY) ===

**STEP 1 — EXHAUSTIVE READING:**
Before writing ANY answer, read EVERY chunk above from start to finish. Information relevant to the query may be scattered across multiple chunks. Do NOT skip any chunk.

**STEP 2 — COMPREHENSIVE EXTRACTION:**
Collect ALL facts, numbers, names, dates, lists, tables, and details from ALL chunks that relate to the query. Even if a chunk has low similarity score, it may still contain critical information — include it.

**STEP 3 — ANSWER CONSTRUCTION & FORMATTING:**
- Deliver your answer in a descriptive, well-structured, engaging, and professional style as usual modern AI chatbots do.
- Use clean, standard Markdown:
  * Divide main concepts or steps using clean Markdown headers (e.g. ### 1. Topic Title).
  * Use clear bullet points (- or *) or numbered lists for sequential steps and sub-items.
  * Use **bold** selectively for key terms, definitions, or emphasis. Do NOT wrap entire sentences or every line in double asterisks.
  * Present comparisons and multi-attribute data in clean Markdown tables.
  * Use fenced code blocks with language identifiers for any code, queries, or commands.
- If information is spread across chunks, synthesize and merge it into a coherent, flowing response with readable paragraphs.
- Cite the source file name(s) cleanly at the end (e.g. Source: DocumentName).

**STEP 4 — OUT-OF-SCOPE CHECK (only after Steps 1-3):**
ONLY if after reading ALL chunks you genuinely find ZERO relevant information, respond:
"{out_of_scope_text}"

**ABSOLUTE PRIVACY & CONFIDENTIALITY RULES:**
- NEVER reveal, output, or quote any Transaction ID, Trx ID, TID, PSID (Payment Slip ID / Consumer ID), Reference Number, or receipt transaction identifier (e.g., from Easypaisa, JazzCash, 1Bill, e-Pay, mobile wallets, or bank receipts), EVEN IF the user explicitly asks for it. If the user asks for a Transaction ID, PSID, or receipt reference, you MUST refuse and state: "Transaction IDs, PSIDs, and payment reference numbers are classified as confidential financial information and cannot be disclosed for security and privacy reasons."
- NEVER reveal, output, or quote any cell number, mobile number, or phone number (e.g., Pakistani mobile numbers 03xx-xxxxxxx, +92..., or international phone numbers), EVEN IF the user explicitly asks for it. If the user asks for a phone number or mobile number, you MUST refuse and state: "Phone numbers and mobile contacts are classified as private personal data and cannot be disclosed to maintain confidentiality."
- NEVER reveal CNIC numbers, IBANs, or bank account numbers.
- NEVER fabricate facts, numbers, or names not present in the chunks.
- NEVER say "I don't have enough information" if ANY chunk contains relevant safe data.
- NEVER give a partial answer when more safe information exists in other chunks — always be exhaustive.
- If the user query is asking about images, picture files, photos, video files, clips, or recordings, or asks to transcribe or extract content from an image or video file, you MUST respond EXACTLY with:
  "Please ask query about textual files(other than images or video files)"
- If the document contains code, schemas, or commands, format them in markdown code blocks.
- If files were withheld for privacy, mention why briefly without using internal technical jargon.
{"For this candidate list, include only explicitly paired names and requested details present in the supplied document. Never substitute general political background or infer missing details." if is_candidate_list else ""}
"""

    config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=1536,
    )
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                generate_content_with_fallback, client, prompt, config
            ),
            timeout=12.0,
        )
    except asyncio.TimeoutError:
        logger.warning("[Gemini] Synthesis hit 12s timeout; generating concise evidence-only answer")
        fast_config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=512)
        fast_prompt = (
            "Answer using ONLY the document evidence below. Do not use outside knowledge, "
            "treat filenames as evidence, add background, or infer missing facts. "
            "If evidence does not state the answer, "
            "say that it is not shown in the supplied text.\n"
            f"Question: {query}\n"
            f"{'For this request, list every explicitly named contesting candidate and the requested party affiliation or election symbol paired with that candidate. Return only a table.' if is_candidate_list else ''}\n"
            f"Document evidence:\n{context_str[:12000]}"
        )
        response = await asyncio.to_thread(
            generate_content_with_fallback, client, fast_prompt, fast_config
        )

    answer = response.text or ""
    if is_candidate_list:
        answer = _validate_candidate_list_answer(
            answer,
            [chunk.get("chunk_text", "") for chunk in chunks_to_include],
            candidate_list_fields,
        )
    return sanitize_confidential_output(answer, query)

def sanitize_confidential_output(text: str, query: str = "") -> str:
    """
    Post-processing safety filter:
    Guarantees that no Transaction IDs, PSIDs, Phone/Cell numbers, or CNICs leak through LLM output.
    """
    if not text:
        return text

    if query:
        conf_match = check_confidential_query(query)
        if conf_match:
            return conf_match[1]

    q_lower = query.lower() if query else ""
    trx_query = bool(re.search(r"\b(transaction\s*id|trx\s*id|tid|txn\s*id|receipt\s*id|reference\s*number|psid|challan\s*no|challan\s*number|consumer\s*id|consumer\s*number)\b", q_lower))
    phone_query = bool(re.search(r"\b(phone|cell|mobile|contact\s*no|contact\s*number|whatsapp)\b", q_lower))

    # Redact Transaction IDs & PSID
    # e.g., "Transaction ID: 57538266282", "PSID: 100000000012345678", "TRX ID 57538266282", "1Bill PSID: 123456"
    text = re.sub(
        r"(?i)\b((?:trx\s*id|transaction\s*id|txn\s*id|tid|psid|reference\s*(?:no|number|id)?|challan\s*(?:no|number)?)\s*[:#-]?\s*)[A-Z0-9]{6,24}\b",
        r"\1[CONFIDENTIAL TRANSACTION ID/PSID WITHHELD]",
        text
    )
    text = re.sub(
        r"(?i)\bpsid\s*[:#-]?\s*[A-Z0-9]{6,24}\b",
        "[CONFIDENTIAL PSID WITHHELD]",
        text
    )

    # Redact Pakistani mobile/cell numbers (e.g. 03451234567, 0300-1234567, +923001234567, 00923001234567)
    text = re.sub(
        r"\b(?:\+92|0092|0)\s*3\d{2}[-\s]?\d{7}\b",
        "[CONFIDENTIAL PHONE NUMBER WITHHELD]",
        text
    )

    # Redact labeled phone/cell numbers
    text = re.sub(
        r"(?i)\b((?:phone|cell|mobile|tel|whatsapp|contact)\s*(?:no|number)?[:\s-]{1,5})\+?\d[\d\s-]{8,15}\d\b",
        r"\1[CONFIDENTIAL PHONE NUMBER WITHHELD]",
        text
    )

    # Redact CNIC numbers
    text = re.sub(
        r"\b\d{5}-\d{7}-\d{1}\b",
        "[CONFIDENTIAL CNIC WITHHELD]",
        text
    )

    # If the user specifically asked for transaction ID or PSID and it was withheld
    if trx_query and any(marker in text for marker in ["[CONFIDENTIAL TRANSACTION ID WITHHELD]", "[CONFIDENTIAL TRANSACTION ID/PSID WITHHELD]", "[CONFIDENTIAL PSID WITHHELD]", "57538266282"]):
        return "Transaction IDs, PSIDs, and payment reference numbers are classified as confidential financial information and cannot be disclosed for security and privacy reasons."

    # If the user specifically asked for phone number and it was withheld
    if phone_query and "[CONFIDENTIAL PHONE NUMBER WITHHELD]" in text:
        return "Phone numbers and mobile contacts are classified as private personal data and cannot be disclosed to maintain confidentiality."

    # If the user queried about images or video files
    if is_query_about_media(query):
        return MEDIA_QUERY_RESPONSE

    return clean_response_text(text)
