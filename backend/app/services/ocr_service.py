"""Optical Character Recognition (OCR) abstraction service with graceful fallback."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("trinetra.ocr")

class OCRService:
    """Provides image and scanned PDF OCR capabilities with Hindi/English support."""

    def __init__(self):
        self._tesseract_available = False
        try:
            import pytesseract
            # Test if tesseract binary can be found
            pytesseract.get_tesseract_version()
            self._tesseract_available = True
        except Exception:
            self._tesseract_available = False

    @property
    def is_available(self) -> bool:
        return self._tesseract_available

    def extract_text_from_image(self, image_bytes: bytes, lang: str = "eng+hin") -> dict[str, Any]:
        """Extracts text from an image (PNG, JPG) with Hindi and English OCR."""
        if not self._tesseract_available:
            return {
                "success": False,
                "text": "",
                "method": "OCR_FALLBACK",
                "notice": "OCR requires Tesseract installation. Scanned image/PDF processed via fallback.",
                "page_count": 1,
            }

        try:
            import pytesseract
            from PIL import Image, ImageOps

            img = Image.open(io.BytesIO(image_bytes))
            # Preprocess: convert to grayscale and enhance contrast
            gray = ImageOps.grayscale(img)
            text = pytesseract.image_to_string(gray, lang=lang)
            return {
                "success": True,
                "text": text.strip(),
                "method": "OCR",
                "notice": "OCR extraction completed successfully.",
                "page_count": 1,
            }
        except Exception as e:
            logger.warning(f"OCR execution failed: {e}")
            return {
                "success": False,
                "text": "",
                "method": "OCR_ERROR",
                "notice": f"OCR processing encountered an error: {str(e)}",
                "page_count": 1,
            }

    def extract_text_from_file(self, file_path: Path) -> dict[str, Any]:
        """Routes file to OCR or text parser based on extension."""
        suffix = file_path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg"}:
            return self.extract_text_from_image(file_path.read_bytes())
        
        # If text file
        if suffix in {".txt", ".csv", ".json"}:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                return {
                    "success": True,
                    "text": content,
                    "method": "DIRECT_READ",
                    "notice": "Direct text extraction completed.",
                    "page_count": 1,
                }
            except Exception as e:
                return {
                    "success": False,
                    "text": "",
                    "method": "READ_ERROR",
                    "notice": f"Failed to read file: {e}",
                    "page_count": 1,
                }

        # PDF extraction fallback (attempts pypdf if available, else fallback)
        if suffix == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                pages_text = []
                for p_idx, page in enumerate(reader.pages):
                    extracted = page.extract_text() or ""
                    if extracted.strip():
                        pages_text.append(extracted)
                if pages_text:
                    return {
                        "success": True,
                        "text": "\n\n".join(pages_text),
                        "method": "PDF_TEXT",
                        "notice": f"Extracted text from {len(pages_text)} PDF page(s).",
                        "page_count": len(pages_text),
                    }
            except Exception:
                pass

        return {
            "success": False,
            "text": "",
            "method": "FALLBACK",
            "notice": "OCR requires Tesseract installation for binary/scanned files.",
            "page_count": 1,
        }
