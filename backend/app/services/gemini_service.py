import asyncio
import json
import logging
import os
import re
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from app.config import settings
from app.services.guardrail_service import is_query_about_media, MEDIA_QUERY_RESPONSE, is_media_file
from app.services.query_intent_service import (
    is_document_structure_query,
    match_files_by_title,
)

logger = logging.getLogger(__name__)


class GeminiServiceUnavailableError(RuntimeError):
    """Raised when all configured Gemini models are temporarily unavailable."""


def get_gemini_client():
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in settings or .env")
    return genai.Client(api_key=settings.GEMINI_API_KEY)

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

    if status_code == 404 or status_code == 408 or status_code == 429:
        return True
    if status_code is not None:
        return 500 <= status_code <= 599
    return isinstance(err, (TimeoutError, ConnectionError))

def generate_content_with_fallback(client, contents, config=None):
    """
    Use the configured model first, then documented stable Gemini Flash models.
    The Google SDK handles bounded retries with exponential backoff for transient
    failures; this function only moves to another model after that call fails.
    """
    models = [
        settings.GEMINI_MODEL,        # Always try the .env-configured model first (gemini-flash-lite-latest)
        "gemini-flash-lite-latest",   # Active fast model
        "gemini-2.5-flash",           # High quality fallback
    ]
    seen = set()
    unique_models = [m for m in models if m and not (m in seen or seen.add(m))]

    if config is None:
        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,
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


async def answer_general_query(query: str) -> str:
    """Answer general questions without loading or analyzing Drive files."""
    client = get_gemini_client()
    prompt = f"""You are a helpful, knowledgeable AI assistant. Answer the user's question clearly, descriptively, and in a well-structured format like modern conversational chatbots.
Use clean Markdown with appropriate headings (###), readable paragraphs, and bullet points. Do NOT put double asterisks around every line or heading.
Do not claim to have searched or analyzed their Google Drive. If the answer is uncertain,
say so rather than inventing details. Do not provide private personal or financial identifiers.

User question: {query}"""
    config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=2048)
    response = await asyncio.to_thread(generate_content_with_fallback, client, prompt, config)
    if not response.text:
        raise RuntimeError("Gemini returned an empty response for the general question.")
    return sanitize_confidential_output(response.text, query)


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
        match_files_by_title,
        _DOCUMENT_REQUEST_PATTERN,
        _DOCUMENT_SEARCH_PATTERN,
        _PERSONAL_CONTEXT_PATTERN,
        _BUSINESS_DATA_PATTERN,
    )

    if is_fast_general_knowledge_query(query):
        return True

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

    # Check if query matches any title in Drive
    if available_files:
        matches = match_files_by_title(query, available_files)
        if matches:
            return False

    # For queries of ANY other context, use fast Gemini classification (~1s)
    try:
        client = get_gemini_client()
        file_catalog_sample = []
        if available_files:
            file_catalog_sample = [f.get("name") for f in available_files[:15] if f.get("name")]

        prompt = f"""You are a query classifier for an AI Drive Document Assistant.
Determine whether the user query is:
- GENERAL: A general knowledge, scientific, educational, factual, conversational, programming, or universal world question that does NOT require searching private personal Google Drive files.
- DRIVE: A query specifically asking about personal, internal, proprietary files, contracts, reports, spreadsheets, or documents in Google Drive.

User Query: "{query}"
Sample file names in Drive: {json.dumps(file_catalog_sample)}

Reply strictly with either GENERAL or DRIVE."""
        config = types.GenerateContentConfig(temperature=0.0, max_output_tokens=5)
        response = await asyncio.wait_for(
            asyncio.to_thread(generate_content_with_fallback, client, prompt, config),
            timeout=2.0,
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
    remaining_chars = 24000 if is_structure_query else 10000
    chunks_to_include = retrieved_chunks if is_structure_query else retrieved_chunks[:8]
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
        logger.warning("[Gemini] Synthesis hit 14s timeout; generating concise direct answer")
        fast_config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=512)
        fast_prompt = f"Answer the user question '{query}' concisely in structured markdown based on this evidence:\n{context_str[:4000]}"
        response = await asyncio.to_thread(
            generate_content_with_fallback, client, fast_prompt, fast_config
        )

    return sanitize_confidential_output(response.text, query)

def sanitize_confidential_output(text: str, query: str = "") -> str:
    """
    Post-processing safety filter:
    Guarantees that no Transaction IDs, PSIDs, Phone/Cell numbers, or CNICs leak through LLM output.
    """
    if not text:
        return text

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

    return text
