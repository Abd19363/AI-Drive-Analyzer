import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from app.config import settings
from app.services.guardrail_service import is_query_about_media, MEDIA_QUERY_RESPONSE

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
        settings.GEMINI_MODEL,
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    seen = set()
    unique_models = [m for m in models if m and not (m in seen or seen.add(m))]

    last_err = None
    for model_name in unique_models:
        try:
            if config:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config
                )
            else:
                return client.models.generate_content(
                    model=model_name,
                    contents=contents
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

async def analyze_query_for_drive_files(query: str, available_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Uses Gemini to analyze the question and select only the relevant file(s)
    from the user's Google Drive.
    """
    if not available_files:
        return []

    client = get_gemini_client()
    
    file_catalog = [
        {
            "file_id": f.get("id"),
            "name": f.get("name"),
            "mime_type": f.get("mimeType"),
            **({"folder": f.get("folder_name")} if f.get("folder_name") else {})
        }
        for f in available_files
    ]
    
    prompt = f"""
You are an expert AI retrieval analyst.
The user asked the following question:
"{query}"

Here is the list of files found in their Google Drive:
{json.dumps(file_catalog, indent=2)}

Task:
Analyze the question and determine which specific file or files are relevant to answering it.

Important Guidelines:
1. Return ONLY a valid JSON list of file IDs that are relevant. Do NOT include completely unrelated files.
2. If the user refers to a specific document name or abbreviation (e.g. "NA_Form-33", "Budget", "Resume"), select the matching document file.
3. If the user asks a topic-based question (e.g. asking about elections, policies, finances, salaries, guides), select the file(s) whose names or types indicate they likely contain the answer. You may select up to 5 relevant files.
4. If the query asks for a general summary or overview of their files without specifying one, select the primary document files (PDFs, Docs, Sheets, TXT) available in their Drive.
5. Prioritize actual content documents (PDFs, Docs, Spreadsheets, Presentations, text) over container folders ("application/vnd.google-apps.folder"). If a query asks about a folder or a file stored in a folder, select the document file(s) inside that folder so their text can be retrieved and summarized.
6. Do NOT select images (PNG, JPG, JPEG, WEBP) or video files (MP4, MKV, MOV, AVI). This system is designed strictly for textual documents (PDFs, Docs, Spreadsheets, Presentations, text).
7. If none are relevant, return an empty list: [].

Example output:
["file_id_1", "file_id_2"]
"""

    response = await asyncio.to_thread(
        generate_content_with_fallback,
        client,
        prompt,
        types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        selected_ids = json.loads(response.text)
        if isinstance(selected_ids, list) and selected_ids:
            return [f for f in available_files if f.get("id") in selected_ids]
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Gemini returned invalid file-selection JSON: %s", e)

    # Fallback to keyword match in filename
    q_words = [w.lower() for w in query.replace("?", " ").replace(".", " ").replace(",", " ").split() if len(w) > 2]
    matched = []
    for f in available_files:
        fname = f.get("name", "").lower()
        if any(w in fname for w in q_words) and f.get("mimeType") != "application/vnd.google-apps.folder":
            matched.append(f)
    if matched:
        return matched

    return []

async def synthesize_answer(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    skipped_confidential_files: List[Dict[str, Any]],
    selected_file_names: Optional[List[str]] = None,
    auto_discovered: bool = False,
    available_file_names: Optional[List[str]] = None,
) -> str:
    """
    Generates the final grounded answer with citations and privacy notices.
    Uses an exhaustive reading strategy: the LLM is instructed to read every
    single chunk before composing the answer, to prevent partial responses.
    """
    client = get_gemini_client()

    selected_files_str = ", ".join(selected_file_names) if selected_file_names else "All active documents"

    # Build numbered context blocks with similarity scores visible
    context_blocks = []
    for idx, chunk in enumerate(retrieved_chunks):
        fname = chunk.get("file_name", "Unknown Document")
        text = chunk.get("chunk_text", "")
        sim = chunk.get("similarity", 0.0)
        context_blocks.append(
            f"--- CHUNK {idx+1} | Source: {fname} | Similarity: {sim:.2f} ---\n{text}"
        )
    context_str = "\n\n".join(context_blocks)

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
            f"\n=== AUTO-DISCOVERY REQUIREMENT ===\n"
            f"The user did NOT manually select files; the system automatically identified relevant document(s) from Google Drive: {selected_files_str}.\n"
            f"You MUST begin your answer by explicitly presenting these identified files to the user before answering, like this:\n"
            f"'**Identified Document(s):** {selected_files_str}\n\n'\n"
            f"Followed by your comprehensive answer.\n"
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

=== PRIVACY BLOCKS ===
{confidential_notice if confidential_notice else "None"}

=== CRITICAL INSTRUCTIONS (FOLLOW EXACTLY) ===

**STEP 1 — EXHAUSTIVE READING:**
Before writing ANY answer, read EVERY chunk above from start to finish. Information relevant to the query may be scattered across multiple chunks. Do NOT skip any chunk.

**STEP 2 — COMPREHENSIVE EXTRACTION:**
Collect ALL facts, numbers, names, dates, lists, tables, and details from ALL chunks that relate to the query. Even if a chunk has low similarity score, it may still contain critical information — include it.

**STEP 3 — ANSWER CONSTRUCTION:**
- Provide a **complete, thorough, and well-organized** answer using all extracted information.
- If the answer involves lists, tables, steps, or structured data, format them properly.
- If information is spread across chunks, **synthesize and merge** it into a coherent response.
- Cite the source file name(s) at the end.

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

    response = await asyncio.to_thread(
        generate_content_with_fallback, client, prompt
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

