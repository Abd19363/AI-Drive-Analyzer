import io
from PIL import Image
import pytesseract
from docx import Document
from app.config import settings

# Configure tesseract executable if needed
if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

def ocr_image_with_gemini_vision(img_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """
    Transcribes text from a scanned document image using Gemini Vision.
    Uses gemini-3.5-flash directly to avoid 503 spikes on flash-lite models.
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
        # Use gemini-3.5-flash which reliably handles vision tasks without 503 errors
        for model_name in ["gemini-3.5-flash", "gemini-flash-latest"]:
            try:
                resp = client.models.generate_content(model=model_name, contents=contents)
                if resp and resp.text:
                    return resp.text.strip()
            except Exception:
                continue
        return ""
    except Exception as e:
        print(f"[OCR Vision Error]: {e}")
        return ""

def extract_text_from_pdf(pdf_bytes: bytes, run_ocr_if_sparse: bool = True, max_ocr_pages: int = 2) -> str:
    """
    Extracts text from PDF bytes using PyMuPDF (fitz) or pypdf.
    If pages contain scanned images and sparse text, optionally runs Gemini Vision OCR
    up to a capped number of pages (max_ocr_pages) to keep response times fast.
    """
    if not pdf_bytes:
        return ""

    extracted_pages = []
    ocr_pages_done = 0

    # 1. Try PyMuPDF (fitz) if available
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_idx, page in enumerate(doc):
            pt = (page.get_text() or "").strip()
            if len(pt) < 40 and run_ocr_if_sparse and ocr_pages_done < max_ocr_pages:
                try:
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("jpeg")
                    ocr_res = ocr_image_with_gemini_vision(img_bytes)
                    if ocr_res:
                        pt = (pt + "\n" + ocr_res).strip()
                        ocr_pages_done += 1
                except Exception:
                    pass
            if pt:
                extracted_pages.append(f"[Page {page_idx + 1}]\n{pt}")
        doc.close()
        if extracted_pages:
            return "\n\n".join(extracted_pages)
    except Exception:
        pass

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

                # If page text is sparse/scanned, inspect page images and run OCR (up to max_ocr_pages)
                if len(page_text) < 40 and run_ocr_if_sparse and ocr_pages_done < max_ocr_pages:
                    page_imgs = getattr(page, "images", [])
                    if page_imgs:
                        for img in page_imgs:
                            try:
                                ocr_res = ocr_image_with_gemini_vision(img.data)
                                if ocr_res:
                                    page_text = (page_text + "\n" + ocr_res).strip()
                                    ocr_pages_done += 1
                                    break  # Primary page image transcribed
                            except Exception as e:
                                print(f"[pypdf OCR error on page {page_idx+1}]: {e}")

                if page_text:
                    extracted_pages.append(f"[Page {page_idx + 1}]\n{page_text}")

        if extracted_pages:
            return "\n\n".join(extracted_pages)
    except Exception as e:
        return f"[PDF Extraction error: {e}]"

    return ""

def extract_text_from_image(image_bytes: bytes) -> str:
    # 1. Try local pytesseract first
    try:
        img = Image.open(io.BytesIO(image_bytes))
        ocr_text = pytesseract.image_to_string(img).strip()
        if ocr_text:
            return ocr_text
    except Exception:
        pass

    # 2. Fallback to Gemini Vision OCR
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

def extract_content(file_bytes: bytes, mime_type: str, file_name: str, run_ocr_if_sparse: bool = True) -> str:
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
        return extract_text_from_pdf(file_bytes, run_ocr_if_sparse=run_ocr_if_sparse)
    elif "image" in mime_type or any(name_lower.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
        if not run_ocr_if_sparse:
            return ""
        return extract_text_from_image(file_bytes)
    elif "wordprocessingml" in mime_type or name_lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif "presentation" in mime_type or name_lower.endswith(".pptx") or name_lower.endswith(".ppt"):
        return extract_text_from_pptx(file_bytes)
    elif mime_type == "application/vnd.google-apps.spreadsheet" or name_lower.endswith(".csv"):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1", errors="ignore").replace("\x00", "")
    elif name_lower.endswith(".xlsx") or "spreadsheetml" in mime_type:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            sheet_texts = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(values_only=True))
                if rows:
                    sheet_lines = [f"[Sheet: {sheet_name}]"]
                    for row in rows:
                        row_vals = [str(c) if c is not None else "" for c in row]
                        if any(v.strip() for v in row_vals):
                            sheet_lines.append(" | ".join(row_vals))
                    sheet_texts.append("\n".join(sheet_lines))
            return "\n\n".join(sheet_texts)
        except Exception:
            return file_bytes.decode("utf-8", errors="ignore")
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
    """Extract only the explicitly requested worksheet, matching its name exactly."""
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    target_name = " ".join(requested_sheet_name.casefold().split())
    actual_name = next(
        (
            name
            for name in workbook.sheetnames
            if " ".join(name.casefold().split()) == target_name
        ),
        None,
    )
    if actual_name is None:
        workbook.close()
        return None

    worksheet = workbook[actual_name]
    lines = [f"[Sheet: {actual_name}]"]
    for row in worksheet.iter_rows(values_only=True):
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
