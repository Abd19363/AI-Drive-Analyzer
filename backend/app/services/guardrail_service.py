import re
from typing import Dict, Any, Tuple
from app.services.extractor_service import extract_content

# 1. Metadata Suspicious Patterns
SENSITIVE_FILENAME_KEYWORDS = [
    ("CNIC", r"\b(cnic|nic|nadra|national[_\s-]?id|id[_\s-]?card)\b"),
    ("SALARY_SLIP", r"\b(salary|payslip|pay[_\s-]?slip|payroll|compensation|allowance[_\s-]?slip)\b"),
    ("PASSPORT", r"\b(passport|visa[_\s-]?copy|citizenship)\b"),
    ("FINANCIAL_STATEMENT", r"\b(balance[_\s-]?sheet|financial[_\s-]?statement|pnl|profit[_\s-]and[_\s-]loss|income[_\s-]?statement|bank[_\s-]?statement|audit[_\s-]?report)\b"),
    ("TAX_DOCUMENT", r"\b(tax[_\s-]?return|w2|1099|fbr[_\s-]?return|ntn[_\s-]?certificate)\b"),
    ("CREDIT_CARD", r"\b(credit[_\s-]?card|debit[_\s-]?card|bank[_\s-]?account)\b"),
    ("CONFIDENTIAL", r"\b(strictly[_\s-]?confidential|classified|secret[_\s-]?contract)\b"),
    ("PAYMENT_RECEIPT", r"\b(easypaisa|easy[_\s-]?paisa|jazzcash|jazz[_\s-]?cash|nayapay|sadapay|upaisa|raast|receipt|transfer[_\s-]?receipt|payment[_\s-]?receipt|transaction[_\s-]?slip|deposit[_\s-]?slip|remittance|money[_\s-]?transfer)\b"),
    ("TRANSACTION_ID", r"\b(trx[_\s-]?id|transaction[_\s-]?id|tid|payment[_\s-]?id|psid|challan|1bill)\b"),
    ("PHONE_NUMBER", r"\b(phone|phones|mobile|mobiles|cell|cells|cell[_\s-]?no|cell[_\s-]?number|cell[_\s-]?numbers|contact[_\s-]?list|phone[_\s-]?book|contacts)\b"),
]

# 2. Content & Regex Validators
REGEX_DETECTORS = {
    "CNIC": [
        # Format 1: 12345-1234567-1 (standard Pakistani CNIC)
        r"\b\d{5}-\d{7}-\d{1}\b",
        # Format 2: 13 contiguous digits preceded by CNIC/NIC/NADRA
        r"(?i)\b(?:cnic|nic|identity\s*no|nadra)[^\d]{1,10}(\d{13})\b"
    ],
    "PASSPORT": [
        # Format: 2 letters followed by 7 digits (e.g., AB1234567) often preceded by passport keyword
        r"(?i)\bpassport(?:\s*no|\s*number)?[^\w]{1,10}([A-Z]{2}\d{7})\b",
        r"(?i)\b[A-Z]{1,2}[0-9]{7,8}\b(?=.*passport)"
    ],
    "SALARY_SLIP": [
        r"(?i)\b(basic\s+salary|gross\s+salary|net\s+pay|gross\s+pay|monthly\s+remuneration)\b",
        r"(?i)\b(total\s+earnings|employee\s+provident\s+fund|tax\s+deducted\s+at\s+source|eob(?:i|)\s+contribution)\b"
    ],
    "FINANCIAL_STATEMENT": [
        r"(?i)\b(balance\s+sheet|statement\s+of\s+financial\s+position|profit\s+and\s+loss\s+statement)\b",
        r"(?i)\b(current\s+assets|total\s+liabilities|shareholders'\s+equity|operating\s+income|ebitda)\b",
        r"(?i)\b(bank\s+statement|account\s+balance|closing\s+balance|opening\s+balance|ledger\s+balance)\b"
    ],
    "BANKING_IBAN": [
        r"\b[A-Z]{2}\d{2}[A-Z0-9]{12,30}\b"
    ],
    "PAYMENT_RECEIPT": [
        r"(?i)\b(?:easypaisa|easy\s*paisa|jazzcash|jazz\s*cash|nayapay|sadapay|upaisa|raast|telenor\s*bank|telenor\s*microfinance)\b",
        r"(?i)\b(?:money\s+transfer\s+receipt|transfer\s+receipt|payment\s+receipt|transaction\s+receipt|deposit\s+slip)\b",
        r"(?i)\b(?:money\s+transfer\s+of\s+rs|transferred\s+to\s+easypaisa|transfer\s+to\s+easypaisa|transfer\s+successful|payment\s+successful)\b"
    ],
    "TRANSACTION_ID": [
        r"(?i)\b(?:trx\s*id|transaction\s*id|txn\s*id|tid|transaction\s*reference|ref\s*no|reference\s*no|reference\s*id|psid|challan\s*no|challan\s*number|consumer\s*id|consumer\s*number)[^\w\n]{1,15}([A-Z0-9]{6,24})\b",
        r"(?i)\btransaction\s*id\s*[:#-]?\s*\d{6,20}\b",
        r"(?i)\btrx\s*id\s*[:#-]?\s*\d{6,20}\b",
        r"(?i)\btid\s*[:#-]?\s*\d{6,20}\b",
        r"(?i)\bpsid\s*[:#-]?\s*[A-Z0-9]{6,24}\b",
        r"(?i)\b(?:1bill|e-?pay)\s*psid\b",
        r"(?i)\bpsid\b"
    ],
    "PHONE_NUMBER": [
        r"(?i)\b(?:cell|mobile|phone|contact|tel|whatsapp)(?:\s*no|\s*number)?[^\d\n]{1,10}(?:\+?92|0092|0)?\s*3\d{2}[-\s]?\d{7}\b",
        r"\b(?:\+92|0092|0)3\d{2}[-\s]?\d{7}\b",
        r"(?i)\b(?:cell|mobile|phone|tel|whatsapp|contact)\s*(?:no|number)?[:\s-]{1,5}\+?\d{1,4}[-.\s]?\(?\d{1,4}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b"
    ]
}

def screen_metadata(filename: str) -> Tuple[bool, str, str]:
    """
    Stage 1: Metadata Screening
    Returns: (is_confidential, reason, detection_type)
    """
    normalized_name = re.sub(r"[\W_]+", " ", filename.lower())
    raw_lower = filename.lower()
    for detection_type, pattern in SENSITIVE_FILENAME_KEYWORDS:
        if re.search(pattern, normalized_name) or re.search(pattern, raw_lower):
            return True, f"Filename '{filename}' matched sensitive pattern for {detection_type}", detection_type
    return False, "", ""

def inspect_content_with_validators(content: str) -> Tuple[bool, str, str, str]:
    """
    Stage 3: Regex & Custom Validators
    Returns: (is_confidential, reason, detection_type, snippet_matched)
    """
    if not content:
        return False, "", "", ""

    # Check each regex detector category
    for detection_type, patterns in REGEX_DETECTORS.items():
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                matched_snippet = match.group(0)
                # Obfuscate snippet for audit log security
                obfuscated = matched_snippet[:3] + "****" + matched_snippet[-2:] if len(matched_snippet) > 5 else "***"
                return True, f"Confidential content detected: {detection_type} pattern matched.", detection_type, obfuscated

    return False, "", "", ""

def evaluate_financial_heuristic(content: str) -> Tuple[bool, str, str]:
    """
    Stage 4: Heuristic keyword density for financial statements, payslips & payment receipts
    """
    lower_content = content.lower()
    financial_terms = [
        "debit", "credit", "balance", "ledger", "invoice", "salary",
        "tax year", "withholding", "annual income", "payroll", "dividend",
        "easypaisa", "jazzcash", "trx id", "transaction id", "transfer amount", "sender name",
        "psid", "challan", "1bill", "consumer id"
    ]
    matches = [term for term in financial_terms if term in lower_content]
    if len(matches) >= 4:
        return True, f"Heuristic density threshold reached for private financial document: found {len(matches)} indicators ({', '.join(matches[:4])}).", "FINANCIAL_DENSITY"
    
    return False, "", ""

def run_guardrails(file_name: str, mime_type: str, file_bytes: bytes) -> Dict[str, Any]:
    """
    Full 4-Layer Guardrail Pipeline:
    1. Metadata Screening
    2. Content Extraction & OCR
    3. Custom Validators & Detectors (CNIC, Salary slip, Passport, IBAN, Financials)
    4. Heuristic / Density Safety Evaluation
    """
    # Stage 1: Metadata Screening
    meta_flagged, meta_reason, meta_type = screen_metadata(file_name)
    if meta_flagged:
        return {
            "is_confidential": True,
            "stage": "METADATA_SCREENING",
            "detection_type": meta_type,
            "reason": meta_reason,
            "snippet": None,
            "confidence": 0.99,
            "extracted_text": ""
        }

    # Stage 2: Content Extraction (including OCR if needed)
    extracted_text = extract_content(file_bytes, mime_type, file_name)

    # Stage 3: Regex & Custom Validators
    val_flagged, val_reason, val_type, snippet = inspect_content_with_validators(extracted_text)
    if val_flagged:
        return {
            "is_confidential": True,
            "stage": "REGEX_VALIDATOR",
            "detection_type": val_type,
            "reason": val_reason,
            "snippet": snippet,
            "confidence": 0.98,
            "extracted_text": extracted_text
        }

    # Stage 4: Heuristic density check
    heur_flagged, heur_reason, heur_type = evaluate_financial_heuristic(extracted_text)
    if heur_flagged:
        return {
            "is_confidential": True,
            "stage": "HEURISTIC_EVALUATOR",
            "detection_type": heur_type,
            "reason": heur_reason,
            "snippet": None,
            "confidence": 0.85,
            "extracted_text": extracted_text
        }

    # Passed all guardrails
    return {
        "is_confidential": False,
        "stage": "ALL_PASSED",
        "detection_type": None,
        "reason": "Document verified safe; no confidential patterns found.",
        "snippet": None,
        "confidence": 1.0,
        "extracted_text": extracted_text
    }

MEDIA_IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff', '.svg', '.ico', '.heic', '.raw')
MEDIA_VIDEO_EXTS = ('.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpeg', '.mpg')
ALL_MEDIA_EXTS = MEDIA_IMAGE_EXTS + MEDIA_VIDEO_EXTS
MEDIA_QUERY_RESPONSE = "Please ask query about textual files(other than images or video files)"

def is_media_file(file_info: dict) -> bool:
    """
    Checks if a file is an image or video based on its name or mime type.
    """
    name = (file_info.get("name") or "").lower()
    mime = (file_info.get("mimeType") or "").lower()
    return (
        mime.startswith("image/")
        or mime.startswith("video/")
        or any(name.endswith(ext) for ext in ALL_MEDIA_EXTS)
    )

def is_query_about_media(query: str) -> bool:
    """
    Detects if the user query is asking about images or video files.
    """
    if not query:
        return False
    q = query.lower().strip()

    # 1. Direct media file extension mentions
    ext_regex = r"\b[\w-]+\.(?:" + "|".join(ext.lstrip(".") for ext in ALL_MEDIA_EXTS) + r")\b"
    if re.search(ext_regex, q):
        return True

    # 2. Check for image/video keywords, ignoring common idioms like 'big picture'
    q_clean = re.sub(r"\b(big|larger|overall|clear|whole|general)\s+picture\b", "", q)

    media_terms = [
        r"\b(?:image|images|video|videos|photo|photos|picture|pictures|pic|pics|recording|recordings|clip|clips|footage|screen\s*recording)\b",
        r"\b(?:mp4|mkv|mov|avi|png|jpg|jpeg|webp)\b"
    ]
    for pattern in media_terms:
        if re.search(pattern, q_clean):
            return True
    return False

