import io
import logging
import time
from functools import wraps

def _log_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.debug(f"{func.__name__} took {elapsed:.2f}s")
        return result
    return wrapper
import os
import shutil
from functools import lru_cache

# Simple in‑memory cache for PDF extraction (keyed by SHA‑256 of the file bytes)
_pdf_extraction_cache: dict[str, str] = {}

import re
import os
import shutil
from pathlib import Path
from PIL import Image
import pytesseract
from docx import Document
from app.config import settings

logger = logging.getLogger(__name__)
DOCUMENT_EXTRACTION_VERSION = 7
# PDF OCR configuration – tuned for speed while keeping accuracy.
PDF_OCR_PAGE_LIMIT = int(os.getenv("PDF_OCR_PAGE_LIMIT", "50"))   # default 50 pages
# Fast OCR mode: if FAST_OCR env var true, lower DPI and page limit for speed
FAST_OCR = os.getenv("FAST_OCR", "false").lower() == "true"
if FAST_OCR:
    PDF_OCR_DPI = 90  # faster rendering
    PDF_OCR_PAGE_LIMIT = 5  # fewer pages OCRed
    logger.info("Fast OCR mode enabled: DPI=%s, page_limit=%s", PDF_OCR_DPI, PDF_OCR_PAGE_LIMIT)
PDF_IMAGE_COVERAGE_THRESHOLD = 0.35
PDF_OCR_DPI = int(os.getenv("PDF_OCR_DPI", "200"))               # default 200 DPI

if settings.TESSERACT_CMD:
    configured_tesseract = shutil.which(settings.TESSERACT_CMD)
    if not configured_tesseract and Path(settings.TESSERACT_CMD).is_file():
        configured_tesseract = settings.TESSERACT_CMD
    if (
        not configured_tesseract
        and os.name == "nt"
        and Path(settings.TESSERACT_CMD).name.lower() == "tesseract"
    ):
        default_tesseract = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Tesseract-OCR"
            / "tesseract.exe"
        )
        if default_tesseract.is_file():
            configured_tesseract = str(default_tesseract)
    pytesseract.pytesseract.tesseract_cmd = (
        configured_tesseract or settings.TESSERACT_CMD
    )


def _ocr_image_with_tesseract(image_bytes: bytes) -> str:
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            return pytesseract.image_to_string(image).strip()
    except Exception as exc:
        logger.warning("Local Tesseract OCR failed: %s", exc)
        return ""


def _ocr_pdf_page(page, allow_vision_fallback: bool = True) -> str:
    pixmap = page.get_pixmap(dpi=PDF_OCR_DPI, alpha=False)
    image_bytes = pixmap.tobytes("png")
    text = _ocr_image_with_tesseract(image_bytes)
    # Run OCR on the page image.
    # If the initial Tesseract extraction yields very little text (<= 8 words),
    # attempt a higher‑quality Gemini Vision OCR fallback.
    if len(text.split()) <= 8 and allow_vision_fallback:
        return ocr_image_with_gemini_vision(image_bytes, mime_type="image/png")
    return text


def pdf_page_needs_ocr(page, extracted_text: str) -> bool:
    if len(extracted_text.strip()) < 40:
        return True

    page_area = page.rect.width * page.rect.height
    if page_area <= 0:
        return False

    image_area = 0.0
    for image_info in page.get_image_info():
        x0, y0, x1, y1 = image_info["bbox"]
        width = max(0.0, min(x1, page.rect.x1) - max(x0, page.rect.x0))
        height = max(0.0, min(y1, page.rect.y1) - max(y0, page.rect.y0))
        image_area += width * height
        if image_area / page_area >= PDF_IMAGE_COVERAGE_THRESHOLD:
            return True
    return False


def ocr_image_with_gemini_vision(
    img_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    max_models: int = 3,
    timeout_seconds: float = 3.5,
) -> str:
    """
    Transcribes text from a scanned document image using Gemini Vision.
    Uses fast flash models with bounded execution.
    """
    try:
        from app.services.gemini_service import get_gemini_client
        from google.genai import types
        client = get_gemini_client()
        contents = [
            types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
            (
                "Transcribe all text from this scanned document page accurately and completely into clean, structured text. "
                "Preserve all tables, columns, rows, names, numbers, symbols, titles, and details verbatim."
            )
        ]
        models = [settings.GEMINI_MODEL, "gemini-2.5-flash", "gemini-flash-latest"]
        seen = set()
        unique_models = [m for m in models if m and not (m in seen or seen.add(m))]
        import concurrent.futures

        def _call_vision(model):
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(max_output_tokens=1024, temperature=0.1),
            )

        for model_name in unique_models[:max_models]:
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = pool.submit(_call_vision, model_name)
            try:
                resp = future.result(timeout=timeout_seconds)
                if resp and resp.text:
                    return resp.text.strip()
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "Gemini Vision OCR timed out for model %s",
                    model_name,
                )
                break
            except Exception:
                continue
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
        return ""
    except Exception as e:
        print(f"[OCR Vision Error]: {e}")
        return ""


def refine_candidate_list_pdf_ocr(
    pdf_bytes: bytes,
    extracted_text: str,
    *,
    max_pages: int = 2,
) -> str:
    page_blocks = re.findall(
        r"\[Page\s+(\d+)\]\s*(.*?)(?=\n\[Page\s+\d+\]|\Z)",
        extracted_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not page_blocks:
        return extracted_text

    candidate_pages = []
    for page_number, page_text in page_blocks:
        if re.search(
            r"\b(?:candidate|candidates|contesting|nominee|nominees|party|"
            r"affiliation|symbol|symbols|NA[\s-]*\d+)\b",
            page_text,
            flags=re.IGNORECASE,
        ):
            candidate_pages.append(int(page_number) - 1)

    if not candidate_pages:
        candidate_pages = [
            int(page_number) - 1
            for page_number, _ in page_blocks[:max_pages]
        ]

    selected_pages = set(candidate_pages[:max_pages])
    if len(selected_pages) < max_pages:
        for page_index in candidate_pages[:max_pages]:
            next_page = page_index + 1
            if next_page < PDF_OCR_PAGE_LIMIT:
                selected_pages.add(next_page)
                if len(selected_pages) >= max_pages:
                    break

    try:
        import fitz
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_index in sorted(selected_pages):
            if page_index >= len(document):
                continue
            page_image = document[page_index].get_pixmap(
                dpi=220,
                alpha=False,
            ).tobytes("png")
            visual_text = ocr_image_with_gemini_vision(
                page_image,
                mime_type="image/png",
                max_models=1,
                timeout_seconds=2.5,
            )
            if visual_text:
                page_number = page_index + 1
                extracted_text = re.sub(
                    rf"(\[Page\s+{page_number}\]\s*)(.*?)(?=\n\[Page\s+\d+\]|\Z)",
                    lambda match: (
                        f"{match.group(1)}{match.group(2).rstrip()}\n"
                        f"[Visual transcription]\n{visual_text}"
                    ),
                    extracted_text,
                    count=1,
                    flags=re.IGNORECASE | re.DOTALL,
                )
        document.close()
    except Exception as exc:
        logger.warning("Candidate-list page OCR refinement failed: %s", exc)

    return extracted_text


@_log_time
def extract_text_from_pdf(
    pdf_bytes: bytes,
    run_ocr_if_sparse: bool = True,
    max_ocr_pages: int = PDF_OCR_PAGE_LIMIT,
    allow_vision_fallback: bool = True,
) -> str:
    """Extract text from a PDF.

    * ``max_ocr_pages`` controls how many pages are sent through OCR.
      If the value is ``0`` or ``-1`` we treat it as *unlimited* and
      automatically use the total number of pages in the document.
    """
    """
    Extracts text from PDF bytes using PyMuPDF (fitz) or pypdf.
    Sparse pages are OCRed locally with Tesseract first, with Gemini Vision as
    a fallback, up to max_ocr_pages.
    """
    if not pdf_bytes:
        return ""

    extracted_pages = []
    ocr_pages_done = 0

    # 1. Try PyMuPDF (fitz) if available
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)
        # If caller requests unlimited OCR (0 or -1), treat as all pages
        if max_ocr_pages in (0, -1):
            max_ocr_pages = total_pages
        for page_idx, page in enumerate(doc):
            pt = (page.get_text() or "").strip()
            if (
                run_ocr_if_sparse
                and ocr_pages_done < max_ocr_pages
                and pdf_page_needs_ocr(page, pt)
            ):
                try:
                    ocr_pages_done += 1
                    ocr_res = _ocr_pdf_page(
                        page,
                        allow_vision_fallback=allow_vision_fallback,
                    )
                    if ocr_res:
                        pt = (pt + "\n" + ocr_res).strip()
                except Exception as exc:
                    logger.warning(
                        "PDF OCR failed on page %s: %s", page_idx + 1, exc
                    )
            if pt:
                extracted_pages.append(f"[Page {page_idx + 1}]\n{pt}")
        doc.close()
        if extracted_pages:
            return "\n\n".join(extracted_pages)
    except Exception as exc:
        logger.warning(
            "PyMuPDF PDF extraction failed; falling back to pypdf: %s",
            exc,
        )

    # 2. Fallback to pypdf (always available)
    try:
        import warnings
        from pypdf import PdfReader
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, message=".*fontTools.*")
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page_idx, page in enumerate(reader.pages):
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, message=".*fontTools.*")
                    page_text = (page.extract_text() or "").strip()

                # OCR embedded scans even when the page also has selectable watermark text.
                if run_ocr_if_sparse and ocr_pages_done < max_ocr_pages:
                    page_imgs = getattr(page, "images", [])
                    if page_imgs:
                        ocr_pages_done += 1
                        image_texts = []
                        for img in page_imgs:
                            try:
                                ocr_res = _ocr_image_with_tesseract(img.data)
                                if len(ocr_res.split()) < 8 and allow_vision_fallback:
                                    ocr_res = ocr_image_with_gemini_vision(img.data)
                                if ocr_res:
                                    image_texts.append(ocr_res)
                            except Exception as e:
                                logger.warning(
                                    "PDF image OCR failed on page %s: %s",
                                    page_idx + 1,
                                    e,
                                )
                        if image_texts:
                            page_text = "\n".join(
                                part for part in (page_text, *image_texts) if part
                            )

                if page_text:
                    extracted_pages.append(f"[Page {page_idx + 1}]\n{page_text}")

        if extracted_pages:
            return "\n\n".join(extracted_pages)
    except Exception as e:
        return f"[PDF Extraction error: {e}]"

    return ""

def extract_text_from_image(image_bytes: bytes) -> str:
    ocr_text = _ocr_image_with_tesseract(image_bytes)
    if ocr_text:
        return ocr_text

    try:
        vision_text = ocr_image_with_gemini_vision(image_bytes)
        if vision_text:
            return vision_text
    except Exception as e:
        return f"[OCR Unavailable: {str(e)}]"

    return ""

def extract_text_from_docx(docx_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(docx_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Also extract table text
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        return "\n".join(paragraphs)
    except Exception as e:
        return f"[DOCX Extraction error: {e}]"

def extract_text_from_pptx(pptx_bytes: bytes) -> str:
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(pptx_bytes))
        slides_text = []
        for idx, slide in enumerate(prs.slides):
            slide_content = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_content.append(shape.text.strip())
            if slide_content:
                slides_text.append(f"--- [Slide {idx+1}] ---\n" + "\n".join(slide_content))
        return "\n\n".join(slides_text)
    except Exception as e:
        try:
            return pptx_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return f"[Presentation extraction error: {e}]"

def extract_content(
    file_bytes: bytes,
    mime_type: str,
    file_name: str,
    run_ocr_if_sparse: bool = True,
    allow_vision_fallback: bool = True,
) -> str:
    if not file_bytes:
        return ""

    name_lower = file_name.lower()
    
    # Check if file is a PDF (by magic bytes %PDF, mime type, extension, or Google Docs/Slides export)
    if (
        file_bytes.startswith(b"%PDF")
        or "pdf" in mime_type
        or name_lower.endswith(".pdf")
        or mime_type in ("application/vnd.google-apps.document", "application/vnd.google-apps.presentation")
    ):
        return extract_text_from_pdf(
            file_bytes,
            run_ocr_if_sparse=run_ocr_if_sparse,
            allow_vision_fallback=allow_vision_fallback,
        )
    elif "image" in mime_type or any(name_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
        if not run_ocr_if_sparse:
            return ""
        return extract_text_from_image(file_bytes)
    elif "wordprocessingml" in mime_type or name_lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif "presentation" in mime_type or name_lower.endswith(".pptx") or name_lower.endswith(".ppt"):
        return extract_text_from_pptx(file_bytes)
    elif (
        mime_type == "application/vnd.google-apps.spreadsheet"
        or name_lower.endswith(".xlsx")
        or "spreadsheetml" in mime_type
        or file_bytes.startswith(b"PK\x03\x04")
    ):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
            sheet_names = wb.sheetnames
            sheet_texts = [f"[Workbook Summary: File contains {len(sheet_names)} Sub-Sheets: {', '.join(sheet_names)}]"]
            for sheet_name in sheet_names:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(max_row=500, values_only=True))
                if rows:
                    sheet_lines = [f"[Sub-Sheet: {sheet_name}]"]
                    for row in rows:
                        row_vals = [str(c) if c is not None else "" for c in row]
                        if any(v.strip() for v in row_vals):
                            sheet_lines.append(" | ".join(row_vals))
                    sheet_texts.append("\n".join(sheet_lines))
            wb.close()
            return "\n\n".join(sheet_texts)
        except Exception:
            return file_bytes.decode("utf-8", errors="ignore")
    elif name_lower.endswith(".csv") or mime_type == "text/csv":
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="ignore").replace("\x00", "")
    else:
        # Fallback to UTF-8 decoding for text, csv, json, md, etc.
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_bytes.decode("latin-1", errors="ignore").replace("\x00", "")
            except Exception:
                return ""


def extract_excel_sheet_text(file_bytes: bytes, requested_sheet_name: str) -> str | None:
    """Extract the requested sub-sheet/worksheet with exact, ordinal, or substring matching."""
    import openpyxl
    import re

    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    clean_req = requested_sheet_name.strip()
    target_name = " ".join(clean_req.casefold().split())

    # 1. Exact case-insensitive match
    actual_name = next(
        (
            name
            for name in workbook.sheetnames
            if " ".join(name.casefold().split()) == target_name
        ),
        None,
    )

    # 2. Check for ordinal sheet references ("first", "second", "1", "2", "last", etc.)
    if actual_name is None and workbook.sheetnames:
        ord_map = {
            "first": 0, "1st": 0, "1": 0, "one": 0,
            "second": 1, "2nd": 1, "2": 1, "two": 1,
            "third": 2, "3rd": 2, "3": 2, "three": 2,
            "fourth": 3, "4th": 3, "4": 3, "four": 3,
            "fifth": 4, "5th": 4, "5": 4, "five": 4,
            "last": -1, "final": -1,
        }
        for token, idx in ord_map.items():
            if re.search(r"\b" + re.escape(token) + r"\b", target_name):
                if -len(workbook.sheetnames) <= idx < len(workbook.sheetnames):
                    actual_name = workbook.sheetnames[idx]
                    break

    # 3. Substring match (e.g. "sales" matches "Sales Data" or "2024_Sales")
    if actual_name is None:
        actual_name = next(
            (
                name
                for name in workbook.sheetnames
                if target_name in name.casefold() or name.casefold() in target_name
            ),
            None,
        )

    if actual_name is None:
        workbook.close()
        return None

    worksheet = workbook[actual_name]
    lines = [f"[Sub-Sheet: {actual_name}]"]
    for row in worksheet.iter_rows(max_row=1000, values_only=True):
        values = [str(cell) if cell is not None else "" for cell in row]
        if any(value.strip() for value in values):
            lines.append(" | ".join(values))
    sheet_text = "\n".join(lines)
    workbook.close()
    return sheet_text


def chunk_text(text: str, chunk_size: int = 900, chunk_overlap: int = 120) -> list[str]:
    """
    Split text into coherent, boundary-aware chunks.
    Respects paragraph breaks and sentence boundaries to avoid slicing words or key data.
    Sanitizes null bytes (\x00) for PostgreSQL safety.
    """
    if not text:
        return []
    
    clean_text = text.replace("\x00", "").strip()
    if not clean_text:
        return []

    # If small enough, return as single chunk
    if len(clean_text) <= chunk_size:
        return [clean_text]

    # Split into structural blocks (paragraphs)
    raw_paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    if not raw_paragraphs:
        raw_paragraphs = [p.strip() for p in clean_text.split("\n") if p.strip()]

    chunks = []
    current_chunk = []
    current_length = 0

    for para in raw_paragraphs:
        # If single paragraph is larger than chunk_size, split by sentences or line breaks
        if len(para) > chunk_size:
            # Sub-split paragraph
            sub_parts = []
            lines = para.split("\n")
            for line in lines:
                if len(line) <= chunk_size:
                    sub_parts.append(line)
                else:
                    # Split on sentence boundaries
                    import re
                    sentences = re.split(r"(?<=[.?!])\s+", line)
                    sub_parts.extend(sentences)

            for part in sub_parts:
                part = part.strip()
                if not part:
                    continue
                if current_length + len(part) > chunk_size and current_chunk:
                    chunks.append("\n".join(current_chunk))
                    # Overlap: keep last piece
                    overlap_piece = current_chunk[-1] if len(current_chunk[-1]) < chunk_overlap else ""
                    current_chunk = [overlap_piece, part] if overlap_piece else [part]
                    current_length = sum(len(c) for c in current_chunk) + len(current_chunk)
                else:
                    current_chunk.append(part)
                    current_length += len(part) + 1
        else:
            if current_length + len(para) > chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                # Add overlap from last paragraph if reasonable length
                overlap_para = current_chunk[-1] if len(current_chunk[-1]) <= chunk_overlap * 2 else ""
                current_chunk = [overlap_para, para] if overlap_para else [para]
                current_length = sum(len(c) for c in current_chunk) + len(current_chunk) * 2
            else:
                current_chunk.append(para)
                current_length += len(para) + 2

    if current_chunk:
        final_str = "\n\n".join(current_chunk).strip()
        if final_str:
            chunks.append(final_str)

    # Clean up empty chunks and ensure no duplicates
    final_chunks = []
    for ch in chunks:
        ch_clean = ch.strip()
        if ch_clean and (not final_chunks or final_chunks[-1] != ch_clean):
            final_chunks.append(ch_clean)

    return final_chunks
